# Modified: [1.1] threading.Lock() on all shared state; [1.3] CF_EXCLUDECLIPBOARDCONTENT check,
#           WM_WTSSESSION_CHANGE re-attach; [1.6] _ignore_next_change flag;
#           [5.6] per-app exclusion list; [5.3] TYPE_EMAIL, TYPE_CODE detection;
#           [2.1] sensitive data masking — image path uses v1.3.4 proven Qt approach
#           [fix] Win+Shift+S: delayed-render retry now not blocked by hasText()
"""Clipboard monitor using Win32 clipboard sequence number for reliable detection."""
import os
import re
import json
import ctypes
import hashlib
import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage

from cyberclip.storage.models import ClipboardItem
from cyberclip.utils.constants import (
    TYPE_TEXT, TYPE_IMAGE, TYPE_FILE, TYPE_URL, TYPE_COLOR,
    TYPE_EMAIL, TYPE_CODE,
)
from cyberclip.core.link_cleaner import clean_url
from cyberclip.utils.sensitive_detector import detect as detect_sensitive

# ---------------------------------------------------------------------------
# Win32 helpers
# ---------------------------------------------------------------------------
_user32 = ctypes.windll.user32

def _get_exclude_clipboard_format() -> int:
    """Dynamically register the CF_ExcludeClipboardContent format used by password managers."""
    try:
        return _user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
    except Exception:
        return 0

_EXCLUDE_FORMAT = _get_exclude_clipboard_format()
# Static sentinel value used by some builds of 1Password / Bitwarden
_CF_EXCLUDE_STATIC = 0xC009

# Win32 image format constants — used to detect images Qt's mime might miss
CF_BITMAP = 2
CF_DIB    = 8
CF_DIBV5  = 17
try:
    _CF_PNG = _user32.RegisterClipboardFormatW("PNG")   # Win+Shift+S / Snipping Tool
except Exception:
    _CF_PNG = 0


def _clipboard_has_exclude_flag() -> bool:
    """
    Return True if the clipboard carries the ExcludeClipboardContent flag set by
    password managers (1Password, Bitwarden, KeePass, …) to signal 'do not record'.
    IsClipboardFormatAvailable does NOT require OpenClipboard.
    """
    try:
        for fmt in (_CF_EXCLUDE_STATIC, _EXCLUDE_FORMAT):
            if fmt and _user32.IsClipboardFormatAvailable(fmt):
                return True
    except Exception:
        pass
    return False


def _win32_has_image() -> bool:
    """
    Check Win32 directly for any image format — more reliable than mime.hasImage()
    for delayed-render sources like Win+Shift+S which may not expose CF_DIB immediately
    but DO register the sequence number change right away.
    """
    try:
        for fmt in (CF_DIBV5, CF_DIB, CF_BITMAP, _CF_PNG):
            if fmt and _user32.IsClipboardFormatAvailable(fmt):
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# WM_WTSSESSION_CHANGE constants (Windows session notifications)
# ---------------------------------------------------------------------------
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK   = 0x8

# ---------------------------------------------------------------------------
# Color / URL / path patterns
# ---------------------------------------------------------------------------
HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
RGB_COLOR_RE  = re.compile(
    r'^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)$'
)
HSL_COLOR_RE  = re.compile(
    r'^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%?\s*,\s*\d{1,3}%?\s*(?:,\s*[\d.]+\s*)?\)$'
)
URL_RE       = re.compile(r'^https?://\S+$', re.IGNORECASE)
FILE_PATH_RE = re.compile(
    r'^[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$', re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Code heuristic (5.3)
# ---------------------------------------------------------------------------
_CODE_INDICATORS = re.compile(
    r'(?:'
    r'^\s*(?:def |class |import |from |#!|\/\/|\/\*|\*\/|<\?php|package |using )'
    r'|(?:\bfunction\b|\bconst\b|\blet\b|\bvar\b)\s+\w+\s*[=(]'
    r'|(?:->|=>|:=|\|\||\&\&|!=|===|!==)'
    r'|^\s*(?:if|for|while|switch|return|throw|catch|try)\s*[\({]'
    r')',
    re.MULTILINE,
)

def _looks_like_code(text: str) -> bool:
    """Heuristic: True if *text* has >= 2 code indicator matches."""
    if '\n' not in text:
        return False
    return len(_CODE_INDICATORS.findall(text)) >= 2


# ---------------------------------------------------------------------------
# ClipboardMonitor
# ---------------------------------------------------------------------------
class ClipboardMonitor(QObject):
    """
    Thread-safe clipboard monitor.

    All QApplication.clipboard() calls happen exclusively on the main thread
    because this object is driven by a QTimer whose timeout fires on the thread
    that created it (the main thread). Shared mutable state is protected by
    ``_lock`` to allow safe writes from other threads (e.g. hotkey thread).
    """
    item_captured    = pyqtSignal(ClipboardItem)
    session_unlocked = pyqtSignal()

    def __init__(self, image_store, parent=None):
        super().__init__(parent)
        self.image_store = image_store

        # ── Shared state — ALL writes MUST hold _lock ──────────────────────
        self._lock                     = threading.Lock()
        self._ghost_mode: bool         = False
        self._blacklist: list          = []
        self._exclusions: list         = []   # 5.6 per-app process name exclusion list
        self._paused: bool             = False
        self._skip_count: int          = 0
        self._ignore_next_change: bool = False   # 1.6 suppress re-capture after paste
        # ───────────────────────────────────────────────────────────────────

        self._last_image_hash: str | None = None
        self._last_text_hash:  str | None = None
        self._retry_seq:       int | None = None   # seq saved for delayed-render retry

        try:
            self._seq_number = _user32.GetClipboardSequenceNumber()
        except Exception:
            self._seq_number = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_clipboard)
        self._timer.start(150)

    # ── Public setters (may be called from any thread) ───────────────────
    def set_ghost_mode(self, enabled: bool):
        with self._lock:
            self._ghost_mode = enabled

    def set_blacklist(self, apps: list):
        with self._lock:
            self._blacklist = [a.lower() for a in apps]

    def set_exclusions(self, process_names: list):
        """5.6 — Set per-app exclusion list (process names, case-insensitive)."""
        with self._lock:
            self._exclusions = [p.lower() for p in process_names]

    def pause(self):
        """Pause monitoring — we're about to modify the clipboard ourselves."""
        with self._lock:
            self._paused = True

    def resume(self):
        """Resume after our own paste; re-sync sequence number to skip our own write."""
        try:
            new_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            new_seq = self._seq_number
        with self._lock:
            self._seq_number         = new_seq
            self._skip_count         = 0
            self._ignore_next_change = False
            self._paused             = False

    def suppress_next(self):
        """1.6 — Call BEFORE writing to clipboard to prevent re-capture of pasted item."""
        with self._lock:
            self._ignore_next_change = True

    def stop(self):
        self._timer.stop()

    # ── Session change handling (1.3) ─────────────────────────────────────
    @pyqtSlot()
    def on_session_unlocked(self):
        """Re-sync sequence number after Windows lock/unlock cycle."""
        try:
            new_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            return
        with self._lock:
            self._seq_number = new_seq
        self.session_unlocked.emit()

    # ── Internal polling (runs on main thread via QTimer) ─────────────────
    def _check_clipboard(self):
        with self._lock:
            paused = self._paused
            ghost  = self._ghost_mode
            skip   = self._skip_count
            ignore = self._ignore_next_change
            if skip > 0:
                self._skip_count -= 1

        if paused or ghost:
            return

        try:
            new_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            return

        if new_seq == self._seq_number:
            return

        self._seq_number = new_seq

        if skip > 0:
            return

        if _clipboard_has_exclude_flag():
            return

        if ignore:
            with self._lock:
                self._ignore_next_change = False
            return

        if self._is_blacklisted():
            return

        if self._is_excluded_app():
            return

        clipboard = QApplication.clipboard()
        mime      = clipboard.mimeData()
        if mime is None:
            return

        try:
            self._process_clipboard(mime, clipboard)
        except Exception as exc:
            logger.debug("clipboard check error: %s", exc)

    def _is_blacklisted(self) -> bool:
        with self._lock:
            blacklist = list(self._blacklist)
        if not blacklist:
            return False
        try:
            from cyberclip.utils.win32_helpers import get_foreground_window_info
            _, title, exe = get_foreground_window_info()
            check = f"{exe or ''} {title or ''}".lower()
            for bl in blacklist:
                if bl in check:
                    return True
        except Exception:
            pass
        return False

    def _is_excluded_app(self) -> bool:
        """5.6 — Return True if the foreground process is in the exclusion list."""
        with self._lock:
            exclusions = list(self._exclusions)
        if not exclusions:
            return False
        try:
            from cyberclip.utils.win32_helpers import get_foreground_window_info
            _, _, exe = get_foreground_window_info()
            if exe:
                exe_lower = exe.lower()
                for ex in exclusions:
                    if ex == exe_lower or exe_lower.endswith(ex):
                        return True
        except Exception:
            pass
        return False

    def _process_clipboard(self, mime, clipboard):
        # ── Priority 1: Image ─────────────────────────────────────────────
        # Check BOTH Qt mime AND Win32 formats. Win+Shift+S registers CF_BITMAP/
        # CF_PNG in Win32 before Qt's mime layer sees it, so _win32_has_image()
        # is the authoritative check here.
        has_image = mime.hasImage() or _win32_has_image()

        if has_image:
            img = clipboard.image()
            if not img.isNull() and img.width() > 0 and img.height() > 0:
                img_hash = self._image_hash(img)
                if img_hash and img_hash == self._last_image_hash:
                    return   # duplicate
                if img_hash:
                    self._last_image_hash = img_hash
                path = self.image_store.save_qimage(img)
                item = ClipboardItem(
                    content_type=TYPE_IMAGE,
                    image_path=path,
                    text_content=f"{img.width()}x{img.height()}",
                    created_at=datetime.now().isoformat(),
                )
                self._detect_source(item)
                self.item_captured.emit(item)
                return
            else:
                # Win32 says image exists but Qt can't read it yet — delayed render.
                # Schedule a single retry; don't fall through to text handling.
                if self._retry_seq is None:
                    self._retry_seq = self._seq_number
                    logger.debug("image formats present but Qt read empty — retrying in 500ms")
                    QTimer.singleShot(500, self._retry_image_capture)
                return

        # ── Priority 2: Files ─────────────────────────────────────────────
        if mime.hasUrls():
            urls       = mime.urls()
            file_paths = [u.toLocalFile() for u in urls
                          if u.isLocalFile() and u.toLocalFile()]
            if file_paths:
                for fp in file_paths:
                    item = ClipboardItem(
                        content_type=TYPE_FILE,
                        text_content=fp,
                        created_at=datetime.now().isoformat(),
                    )
                    self._detect_source(item)
                    self.item_captured.emit(item)
            return

        # ── Priority 3: Text ──────────────────────────────────────────────
        if mime.hasText():
            text = mime.text()
            if text and text.strip():
                text      = text.strip()
                text_hash = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
                if text_hash == self._last_text_hash:
                    return
                self._last_text_hash = text_hash
                item = self._classify_text(text)
                self._detect_source(item)
                self.item_captured.emit(item)

    @pyqtSlot()
    def _retry_image_capture(self):
        """
        One-shot retry for delayed-render screenshots (Win+Shift+S).
        Only proceeds if no other clipboard change occurred during the 500ms wait.
        """
        saved_seq       = self._retry_seq
        self._retry_seq = None   # consume — only one retry per event

        if saved_seq is None:
            return

        try:
            current_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            return

        if current_seq != saved_seq:
            # Another clipboard change happened — normal polling will handle it.
            return

        clipboard = QApplication.clipboard()
        mime      = clipboard.mimeData()
        if mime is None:
            return

        if not mime.hasImage() and not _win32_has_image():
            logger.debug("retry: still no image format available — giving up")
            return

        img = clipboard.image()
        if img.isNull() or img.width() <= 0 or img.height() <= 0:
            logger.debug("retry: Qt image still null after 500ms — giving up")
            return

        img_hash = self._image_hash(img)
        if img_hash and img_hash == self._last_image_hash:
            return   # duplicate
        if img_hash:
            self._last_image_hash = img_hash

        path = self.image_store.save_qimage(img)
        item = ClipboardItem(
            content_type=TYPE_IMAGE,
            image_path=path,
            text_content=f"{img.width()}x{img.height()}",
            created_at=datetime.now().isoformat(),
        )
        self._detect_source(item)
        logger.info("delayed-render image captured on retry (%dx%d)", img.width(), img.height())
        self.item_captured.emit(item)

    # ── Text classification ───────────────────────────────────────────────
    def _classify_text(self, text: str) -> ClipboardItem:
        if HEX_COLOR_RE.match(text) or RGB_COLOR_RE.match(text) or HSL_COLOR_RE.match(text):
            return ClipboardItem(
                content_type=TYPE_COLOR,
                text_content=text,
                extra_data=json.dumps({"color": text}),
                created_at=datetime.now().isoformat(),
            )
        if URL_RE.match(text):
            cleaned = clean_url(text)
            return ClipboardItem(
                content_type=TYPE_URL,
                text_content=cleaned,
                extra_data=json.dumps({"original_url": text}) if cleaned != text else "",
                created_at=datetime.now().isoformat(),
            )
        if FILE_PATH_RE.match(text) and os.path.exists(text):
            return ClipboardItem(
                content_type=TYPE_FILE,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )
        if re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', text):
            return ClipboardItem(
                content_type=TYPE_EMAIL,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )
        sensitive_flag, display_text = detect_sensitive(text)
        if sensitive_flag:
            return ClipboardItem(
                content_type=TYPE_TEXT,
                text_content=display_text,
                is_sensitive=True,
                created_at=datetime.now().isoformat(),
            )
        if _looks_like_code(text):
            return ClipboardItem(
                content_type=TYPE_CODE,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )
        return ClipboardItem(
            content_type=TYPE_TEXT,
            text_content=text,
            created_at=datetime.now().isoformat(),
        )

    def _detect_source(self, item: ClipboardItem):
        try:
            from cyberclip.utils.win32_helpers import get_foreground_window_info
            _, title, exe = get_foreground_window_info()
            item.source_app = exe or title or ""
        except Exception:
            pass

    def _image_hash(self, img) -> str | None:
        """MD5 of QImage pixel data using bytesPerLine()*height() — reliable in PyQt6."""
        try:
            size = img.bytesPerLine() * img.height()
            if size <= 0:
                return None
            ptr = img.bits()
            if ptr is None:
                return None
            ptr.setsize(size)
            raw = bytes(ptr)
            return hashlib.md5(raw).hexdigest() if raw else None
        except Exception as exc:
            logger.debug("_image_hash error: %s", exc)
            return None