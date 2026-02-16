"""Clipboard monitor using Win32 clipboard sequence number for reliable detection."""
import os
import re
import json
import ctypes
import hashlib
from datetime import datetime

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage

from cyberclip.storage.models import ClipboardItem
from cyberclip.utils.constants import (
    TYPE_TEXT, TYPE_IMAGE, TYPE_FILE, TYPE_URL, TYPE_COLOR,
    TRACKING_PARAMS,
)

# Color detection patterns
HEX_COLOR_RE = re.compile(r'^#(?:[0-9a-fA-F]{3}){1,2}$')
RGB_COLOR_RE = re.compile(r'^rgba?\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*[\d.]+\s*)?\)$')
HSL_COLOR_RE = re.compile(r'^hsla?\(\s*\d{1,3}\s*,\s*\d{1,3}%?\s*,\s*\d{1,3}%?\s*(?:,\s*[\d.]+\s*)?\)$')
URL_RE = re.compile(r'^https?://\S+$', re.IGNORECASE)
FILE_PATH_RE = re.compile(r'^[A-Z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*$', re.IGNORECASE)


class ClipboardMonitor(QObject):
    item_captured = pyqtSignal(ClipboardItem)

    def __init__(self, image_store, parent=None):
        super().__init__(parent)
        self.image_store = image_store
        self._ghost_mode = False
        self._blacklist = []
        self._paused = False
        self._skip_count = 0

        # Use Win32 clipboard sequence number — changes every time ANY app modifies clipboard
        try:
            self._seq_number = ctypes.windll.user32.GetClipboardSequenceNumber()
        except Exception:
            self._seq_number = 0

        # Fast polling at 150ms for reliable capture
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_clipboard)
        self._timer.start(150)

    def set_ghost_mode(self, enabled: bool):
        self._ghost_mode = enabled

    def set_blacklist(self, apps: list):
        self._blacklist = [a.lower() for a in apps]

    def _is_blacklisted(self) -> bool:
        if not self._blacklist:
            return False
        try:
            from cyberclip.utils.win32_helpers import get_foreground_window_info
            _, title, exe = get_foreground_window_info()
            check = f"{exe or ''} {title or ''}".lower()
            for bl in self._blacklist:
                if bl in check:
                    return True
        except Exception:
            pass
        return False

    def _check_clipboard(self):
        if self._paused or self._ghost_mode:
            return

        # Check Win32 sequence number — only fires when clipboard ACTUALLY changes
        try:
            new_seq = ctypes.windll.user32.GetClipboardSequenceNumber()
        except Exception:
            return

        if new_seq == self._seq_number:
            return  # Nothing changed

        self._seq_number = new_seq

        # Skip cycles caused by our own paste operations
        if self._skip_count > 0:
            self._skip_count -= 1
            return

        if self._is_blacklisted():
            return

        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is None:
            return

        try:
            self._process_clipboard(mime, clipboard)
        except Exception:
            pass

    def _process_clipboard(self, mime, clipboard):
        # Priority 1: Image (check before text since images often also have text)
        if mime.hasImage():
            img = clipboard.image()
            if not img.isNull() and img.width() > 0 and img.height() > 0:
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
                item = self._classify_text(text)
                self._detect_source(item)
                self.item_captured.emit(item)

    def _classify_text(self, text: str) -> ClipboardItem:
        # Color codes
        if HEX_COLOR_RE.match(text) or RGB_COLOR_RE.match(text) or HSL_COLOR_RE.match(text):
            return ClipboardItem(
                content_type=TYPE_COLOR,
                text_content=text,
                extra_data=json.dumps({"color": text}),
                created_at=datetime.now().isoformat(),
            )

        # URLs
        if URL_RE.match(text):
            cleaned = self._clean_url(text)
            return ClipboardItem(
                content_type=TYPE_URL,
                text_content=cleaned,
                extra_data=json.dumps({"original_url": text}) if cleaned != text else "",
                created_at=datetime.now().isoformat(),
            )

        # File paths
        if FILE_PATH_RE.match(text) and os.path.exists(text):
            return ClipboardItem(
                content_type=TYPE_FILE,
                text_content=text,
                created_at=datetime.now().isoformat(),
            )

        return ClipboardItem(
            content_type=TYPE_TEXT,
            text_content=text,
            created_at=datetime.now().isoformat(),
        )

    def _clean_url(self, url: str) -> str:
        try:
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            cleaned = {k: v for k, v in params.items()
                       if k.lower() not in TRACKING_PARAMS}
            new_query = urlencode(cleaned, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        except Exception:
            return url

    def _detect_source(self, item: ClipboardItem):
        try:
            from cyberclip.utils.win32_helpers import get_foreground_window_info
            _, title, exe = get_foreground_window_info()
            item.source_app = exe or title or ""
        except Exception:
            pass

    def pause(self):
        """Pause monitoring and skip the next 2 sequence changes (from our paste)."""
        self._paused = True

    def resume(self):
        """Resume monitoring, re-sync the sequence number so we don't capture our own paste."""
        try:
            self._seq_number = ctypes.windll.user32.GetClipboardSequenceNumber()
        except Exception:
            pass
        self._skip_count = 1
        self._paused = False

    def stop(self):
        self._timer.stop()
