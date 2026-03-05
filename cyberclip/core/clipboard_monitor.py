# Modified: [1.1] threading.Lock() on all shared state; [1.3] CF_EXCLUDECLIPBOARDCONTENT check,
#           OpenClipboard retry logic, WM_WTSSESSION_CHANGE re-attach;
#           [1.6] _ignore_next_change flag to suppress re-capture after paste-from-history
"""Clipboard monitor using Win32 clipboard sequence number for reliable detection."""
import os
import re
import json
import ctypes
import hashlib
import threading
import time
from datetime import datetime

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
# Win32 clipboard format constants
# ---------------------------------------------------------------------------
CF_EXCLUDECLIPBOARDCONTENT = 0xC009   # used by password managers (1Password, Bitwarden)
# (RegisterClipboardFormatW returns a dynamic value; the above is only used as a sentinel
#  in some builds – we also check the dynamic registration)

# Color detection patterns
HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
RGB_COLOR_RE = re.compile(
    r'^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)$'
)
HSL_COLOR_RE = re.compile(
    r'^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%?\s*,\s*\d{1,3}%?\s*(?:,\s*[\d.]+\s*)?\)$'
)
URL_RE = re.compile(r'^https?://\S+$', re.IGNORECASE)
FILE_PATH_RE = re.compile(
    r'^[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$', re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Helpers — OpenClipboard with retry
# ---------------------------------------------------------------------------
_user32 = ctypes.windll.user32

def _open_clipboard_with_retry(hwnd=None, retries: int = 3, delay_ms: int = 50) -> bool:
    """Try to open the clipboard up to *retries* times, sleeping *delay_ms* between attempts."""
    for attempt in range(retries):
        if _user32.OpenClipboard(hwnd):
            return True
        if attempt < retries - 1:
            time.sleep(delay_ms / 1000.0)
    return False


def _get_exclude_clipboard_format() -> int:
    """Dynamically register (or look up) the CF_ExcludeClipboardContent format."""
    try:
        return _user32.RegisterClipboardFormatW("ExcludeClipboardContentFromMonitorProcessing")
    except Exception:
        return 0


_EXCLUDE_FORMAT = _get_exclude_clipboard_format()


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
    """Heuristic: True if *text* has ≥2 code indicator matches."""
    if '\n' not in text:
        return False
    return len(_CODE_INDICATORS.findall(text)) >= 2


def _clipboard_has_exclude_flag() -> bool:
    """
    Return True if the current clipboard data carries the ExcludeClipboardContent
    format that password managers (1Password, Bitwarden, KeePass, …) set to signal
    'do not record this in clipboard history'.
    """
    try:
        if not _open_clipboard_with_retry():
            return False
        try:
            # Check both the hardcoded and dynamically registered formats
            for fmt in (CF_EXCLUDECLIPBOARDCONTENT, _EXCLUDE_FORMAT):
                if fmt and _user32.IsClipboardFormatAvailable(fmt):
                    return True
        finally:
            _user32.CloseClipboard()
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# WM_WTSSESSION_CHANGE constants (Windows session notifications)
# ---------------------------------------------------------------------------
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8


class ClipboardMonitor(QObject):
    """
    Thread-safe clipboard monitor.

    All QApplication.clipboard() calls happen exclusively on the main thread
    because this object is driven by a QTimer whose timeout fires on the thread
    that created it (the main thread). Shared mutable state is protected by
    ``_lock`` to allow safe writes from other threads (e.g. hotkey thread).
    """
    item_captured = pyqtSignal(ClipboardItem)
    # Emitted when monitor re-syncs after a Windows session unlock
    session_unlocked = pyqtSignal()

    def __init__(self, image_store, parent=None):
        super().__init__(parent)
        self.image_store = image_store

        # ── Shared state — ALL writes MUST hold _lock ──────────────────────
        self._lock = threading.Lock()
        self._ghost_mode: bool = False
        self._blacklist: list = []
        self._exclusions: list = []     # 5.6 — per-app process name exclusion list
        self._paused: bool = False
        self._skip_count: int = 0
        self._ignore_next_change: bool = False   # 1.6 – set before we write clipboard
        # ───────────────────────────────────────────────────────────────────

        self._last_image_hash: str | None = None
        self._last_text_hash: str | None = None

        # Use Win32 clipboard sequence number — changes every time ANY app modifies clipboard
        try:
            self._seq_number = _user32.GetClipboardSequenceNumber()
        except Exception:
            self._seq_number = 0

        # Fast polling at 150 ms for reliable capture (QTimer fires on main thread)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_clipboard)
        self._timer.start(150)

    # ── Public setters (called from any thread) ──────────────────────────
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
        """Resume after our own paste, skipping the sequence numbers we produced."""
        try:
            new_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            new_seq = self._seq_number
        with self._lock:
            self._seq_number = new_seq
            self._skip_count = 2        # skip at least 2 seq changes from our set+paste
            self._ignore_next_change = False
            self._paused = False

    def suppress_next(self):
        """
        1.6 — Call BEFORE putting data on the clipboard to prevent the item
        from being re-added to history when pasting from history.
        """
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
        # Read volatile flags under lock then release before doing clipboard work
        with self._lock:
            paused = self._paused
            ghost = self._ghost_mode
            skip = self._skip_count
            ignore = self._ignore_next_change
            if skip > 0:
                self._skip_count -= 1

        if paused or ghost:
            return

        # Sequence number check — only fires when clipboard ACTUALLY changes
        try:
            new_seq = _user32.GetClipboardSequenceNumber()
        except Exception:
            return

        if new_seq == self._seq_number:
            return  # Nothing changed

        self._seq_number = new_seq

        if skip > 0:
            return  # Our own paste caused this change

        # 1.3 — Respect ExcludeClipboardContent flag (set by password managers)
        if _clipboard_has_exclude_flag():
            return

        # 1.6 — Suppress re-capture when we put data on clipboard for pasting
        if ignore:
            with self._lock:
                self._ignore_next_change = False
            return

        if self._is_blacklisted():
            return

        # 5.6 — Per-app exclusion list check
        if self._is_excluded_app():
            return

        # QApplication.clipboard() — SAFE: this runs on the main thread via QTimer
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is None:
            return

        try:
            self._process_clipboard(mime, clipboard)
        except Exception:
            pass

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
        # Priority 1: Image (check before text since images often also have text)
        if mime.hasImage():
            img = clipboard.image()
            if not img.isNull() and img.width() > 0 and img.height() > 0:
                ptr = img.bits()
                if ptr is not None:
                    try:
                        ptr.setsize(img.sizeInBytes())
                        img_hash = hashlib.md5(bytes(ptr)).hexdigest()
                        if img_hash == self._last_image_hash:
                            return
                        self._last_image_hash = img_hash
                    except Exception:
                        pass
                path = self.image_store.save_qimage(img)
                item = ClipboardItem(
                    content_type=TYPE_IMAGE,
                    image_path=path,
                    text_content=f"{img.width()}×{img.height()}",
                    created_at=datetime.now().isoformat(),
                )
                self._detect_source(item)
                self.item_captured.emit(item)
                return

        # Priority 2: Files (from Explorer copy)
        if mime.hasUrls():
            urls = mime.urls()
            file_paths = [u.toLocalFile() for u in urls if u.isLocalFile() and u.toLocalFile()]
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

        # Priority 3: Text
        if mime.hasText():
            text = mime.text()
            if text and text.strip():
                text = text.strip()
                text_hash = hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()
                if text_hash == self._last_text_hash:
                    return
                self._last_text_hash = text_hash
                item = self._classify_text(text)
                self._detect_source(item)
                self.item_captured.emit(item)

    def _classify_text(self, text: str) -> ClipboardItem:
        # Color detection
        if HEX_COLOR_RE.match(text) or RGB_COLOR_RE.match(text) or HSL_COLOR_RE.match(text):
            return ClipboardItem(
                content_type=TYPE_COLOR,
                text_content=text,
                extra_data=json.dumps({"color": text}),
                created_at=datetime.now().isoformat(),
            )
        # URL detection
        if URL_RE.match(text):
            cleaned = clean_url(text)
            return ClipboardItem(
                content_type=TYPE_URL,
                text_content=cleaned,
                extra_data=json.dumps({"original_url": text}) if cleaned != text else "",
                created_at=datetime.now().isoformat(),
            )
        # File path detection
        if FILE_PATH_RE.match(text) and os.path.exists(text):
            return ClipboardItem(
                content_type=TYPE_FILE,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )
        # 5.3 — Email detection
        if re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', text):
            return ClipboardItem(
                content_type=TYPE_EMAIL,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )
        # 2.1 — Sensitive data detection (run before saving plain text)
        sensitive_flag, display_text = detect_sensitive(text)
        if sensitive_flag:
            return ClipboardItem(
                content_type=TYPE_TEXT,
                text_content=display_text,  # store masked version only
                is_sensitive=True,
                created_at=datetime.now().isoformat(),
            )
        # 5.3 — Code detection (heuristic: contains common code patterns)
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
