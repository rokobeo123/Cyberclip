# Modified: [1.1] threading.Lock() on all shared state; [1.3] CF_EXCLUDECLIPBOARDCONTENT check,
#           OpenClipboard retry logic, WM_WTSSESSION_CHANGE re-attach;
#           [1.6] _ignore_next_change flag to suppress re-capture after paste-from-history
"""Clipboard monitor using Win32 clipboard sequence number for reliable detection."""
import os
import re
import json
import ctypes
import hashlib
import logging
import threading
import time
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
# Win32 clipboard format constants
# ---------------------------------------------------------------------------
CF_EXCLUDECLIPBOARDCONTENT = 0xC009   # used by password managers (1Password, Bitwarden)
# (RegisterClipboardFormatW returns a dynamic value; the above is only used as a sentinel
#  in some builds – we also check the dynamic registration)

# Standard Win32 image formats
CF_BITMAP  = 2
CF_DIB     = 8
CF_DIBV5   = 17

# Pre-register custom image formats used by modern Windows apps:
# Win+Shift+S / Snipping Tool put the screenshot as "PNG" registered format;
# CF_DIB is only a Windows-synthesized alias and GetClipboardData(CF_DIB) can
# silently fail when the primary data is a registered PNG.
try:
    _user32_tmp = ctypes.windll.user32
    _CF_PNG  = _user32_tmp.RegisterClipboardFormatW("PNG")    # Win+Shift+S, Snipping Tool
    _CF_JFIF = _user32_tmp.RegisterClipboardFormatW("JFIF")   # some cameras / apps
    del _user32_tmp
except Exception:
    _CF_PNG = _CF_JFIF = 0

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
_kernel32 = ctypes.windll.kernel32

# Set correct return types for Win32 functions that return HANDLE / pointer —
# ctypes defaults to c_int (32-bit) which truncates 64-bit handles on x64 Windows.
_user32.GetClipboardData.restype  = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_kernel32.GlobalLock.restype      = ctypes.c_void_p
_kernel32.GlobalLock.argtypes     = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype    = ctypes.c_bool
_kernel32.GlobalUnlock.argtypes   = [ctypes.c_void_p]
_kernel32.GlobalSize.restype      = ctypes.c_size_t
_kernel32.GlobalSize.argtypes     = [ctypes.c_void_p]

def _open_clipboard_with_retry(hwnd=None, retries: int = 3, delay_ms: int = 50) -> bool:
    """Try to open the clipboard up to *retries* times, sleeping *delay_ms* between attempts."""
    for attempt in range(retries):
        if _user32.OpenClipboard(hwnd):
            return True
        if attempt < retries - 1:
            time.sleep(delay_ms / 1000.0)
    return False


def _read_clipboard_format_bytes(fmt: int) -> bytes | None:
    """
    Read raw bytes from a specific Win32 clipboard format (e.g. registered 'PNG').
    Uses _kernel32 with corrected restype so 64-bit handles are NOT truncated.
    Win+Shift+S / Snipping Tool store the screenshot as the registered 'PNG' format;
    reading it directly bypasses the broken CF_DIB synthesis path.
    """
    if not fmt or not _user32.IsClipboardFormatAvailable(fmt):
        return None
    if not _open_clipboard_with_retry():
        return None
    try:
        h = _user32.GetClipboardData(fmt)   # c_void_p — correct 64-bit handle
        if not h:
            return None
        p = _kernel32.GlobalLock(h)         # c_void_p — correct 64-bit pointer
        if not p:
            return None
        try:
            size = _kernel32.GlobalSize(h)  # c_size_t — correct on 64-bit
            if size <= 0:
                return None
            return bytes((ctypes.c_char * size).from_address(p))
        finally:
            _kernel32.GlobalUnlock(h)
    except Exception as exc:
        logger.debug("_read_clipboard_format_bytes(fmt=%d) error: %s", fmt, exc)
        return None
    finally:
        try:
            _user32.CloseClipboard()
        except Exception:
            pass


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
    NOTE: IsClipboardFormatAvailable does NOT require OpenClipboard — calling
    OpenClipboard here was causing lazy-render clipboard sources (screenshots, some
    apps) to fail when Qt tried to read them immediately after.
    """
    try:
        for fmt in (CF_EXCLUDECLIPBOARDCONTENT, _EXCLUDE_FORMAT):
            if fmt and _user32.IsClipboardFormatAvailable(fmt):
                return True
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
        self._retry_pending: bool = False   # True while a delayed-render retry is queued

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
            self._skip_count = 0
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
        # Use Win32 IsClipboardFormatAvailable as authoritative check —
        # mime.hasImage() can miss CF_BITMAP / CF_DIB from screenshots and
        # some apps even when the data is valid.
        # Also check the registered 'PNG' format used by Win+Shift+S / Snipping Tool.
        has_image = mime.hasImage() or any(
            _user32.IsClipboardFormatAvailable(f)
            for f in (CF_DIBV5, CF_DIB, CF_BITMAP, _CF_PNG, _CF_JFIF) if f
        )

        if has_image:
            if self._try_capture_image(clipboard):
                return
            # All attempts failed but has_image=True → Snipping Tool / delayed render.
            # Schedule a single retry 500 ms later (gives the source app time to render).
            if not self._retry_pending:
                self._retry_pending = True
                logger.info("image formats detected but all reads failed; retrying in 500 ms")
                QTimer.singleShot(500, self._retry_image_capture)
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

    @pyqtSlot()
    def _retry_image_capture(self):
        """Retry image capture after a short delay (handles delayed-rendering sources)."""
        self._retry_pending = False
        clipboard = QApplication.clipboard()
        if self._try_capture_image(clipboard):
            return
        logger.info("image retry also failed — clipboard image not readable")

    def _try_capture_image(self, clipboard) -> bool:
        """
        Try all methods to read a clipboard image.
        Returns True and emits item_captured if successful, False otherwise.

        Order of attempts (mirrors v1.3.4 proven behavior + adds fallbacks):
        1) Qt clipboard.image()  ← primary: works for Win+Shift+S, screen captures, most apps
        2) PIL ImageGrab         ← fallback when Qt image is null but CF_DIB/CF_DIBV5 is present
        3) Win32 registered PNG  ← final: for sources that expose ONLY registered 'PNG' format
        """
        import io as _io
        try:
            from PIL import Image as PILImage, ImageGrab
        except ImportError:
            PILImage = ImageGrab = None

        # ── Attempt 1: Qt native (v1.3.4 approach — reliable for Win+Shift+S) ───────
        try:
            img = clipboard.image()
            if not img.isNull() and img.width() > 0 and img.height() > 0:
                img_hash = self._image_hash(img)
                if img_hash and img_hash == self._last_image_hash:
                    return True   # duplicate
                if img_hash:
                    self._last_image_hash = img_hash
                path = self.image_store.save_qimage(img)
                item = ClipboardItem(
                    content_type=TYPE_IMAGE,
                    image_path=path,
                    text_content=f"{img.width()}\u00d7{img.height()}",
                    created_at=datetime.now().isoformat(),
                )
                self._detect_source(item)
                logger.info("image captured via Qt (%dx%d)", img.width(), img.height())
                self.item_captured.emit(item)
                return True
        except Exception as exc:
            logger.debug("Attempt 1 (Qt image): %s", exc)

        # ── Attempt 2: PIL ImageGrab (CF_DIBv5/CF_DIB — common for GDI/legacy apps) ─
        if PILImage is not None and ImageGrab is not None:
            try:
                pil_img = ImageGrab.grabclipboard()
                if isinstance(pil_img, PILImage.Image):
                    buf = _io.BytesIO()
                    out = (pil_img.convert("RGB")
                           if pil_img.mode not in ("RGB", "RGBA") else pil_img)
                    out.save(buf, "PNG")
                    img_data = buf.getvalue()
                    img_hash = hashlib.md5(img_data).hexdigest()
                    if img_hash == self._last_image_hash:
                        return True   # duplicate
                    self._last_image_hash = img_hash
                    path = self.image_store.save_image(img_data)
                    item = ClipboardItem(
                        content_type=TYPE_IMAGE,
                        image_path=path,
                        text_content=f"{pil_img.width}\u00d7{pil_img.height}",
                        created_at=datetime.now().isoformat(),
                    )
                    self._detect_source(item)
                    logger.info("image captured via PIL/ImageGrab (%dx%d)",
                                pil_img.width, pil_img.height)
                    self.item_captured.emit(item)
                    return True
            except Exception as exc:
                logger.debug("Attempt 2 (PIL ImageGrab): %s", exc)

        # ── Attempt 3: Win32 registered PNG/JFIF bytes ───────────────────────────────
        # For apps that put ONLY a registered 'PNG' format with no CF_DIB synthesis.
        if PILImage is not None:
            for raw_fmt, fmt_name in [(_CF_PNG, "PNG"), (_CF_JFIF, "JFIF")]:
                if not raw_fmt or not _user32.IsClipboardFormatAvailable(raw_fmt):
                    continue
                raw = _read_clipboard_format_bytes(raw_fmt)
                if not raw or len(raw) < 8:
                    continue
                try:
                    pil_img = PILImage.open(_io.BytesIO(raw))
                    img_hash = hashlib.md5(raw).hexdigest()
                    if img_hash == self._last_image_hash:
                        return True   # duplicate
                    self._last_image_hash = img_hash
                    buf = _io.BytesIO()
                    out = (pil_img.convert("RGB")
                           if pil_img.mode not in ("RGB", "RGBA") else pil_img)
                    out.save(buf, "PNG")
                    path = self.image_store.save_image(buf.getvalue())
                    item = ClipboardItem(
                        content_type=TYPE_IMAGE,
                        image_path=path,
                        text_content=f"{pil_img.width}\u00d7{pil_img.height}",
                        created_at=datetime.now().isoformat(),
                    )
                    self._detect_source(item)
                    logger.info("image captured via Win32/%s (%dx%d)",
                                fmt_name, pil_img.width, pil_img.height)
                    self.item_captured.emit(item)
                    return True
                except Exception as exc:
                    logger.debug("Attempt 3 Win32/%s decode error: %s", fmt_name, exc)

        return False   # all attempts failed

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

    def _image_hash(self, img) -> str | None:
        """Compute MD5 of QImage pixel data.  Uses bytesPerLine()*height() which is
        reliable in PyQt6 — sizeInBytes() can return 0 for some image formats."""
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
