"""Safety net - backup and restore clipboard state."""
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage
from PyQt6.QtCore import QMimeData


class SafetyNet:
    def __init__(self):
        self._backup_text = None
        self._backup_image = None
        self._backup_urls = None

    def backup(self):
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        if mime is None:
            return

        if mime.hasText():
            self._backup_text = mime.text()
        if mime.hasImage():
            self._backup_image = QImage(clipboard.image())
        if mime.hasUrls():
            self._backup_urls = list(mime.urls())

    def restore(self):
        clipboard = QApplication.clipboard()
        mime = QMimeData()

        if self._backup_image and not self._backup_image.isNull():
            clipboard.setImage(self._backup_image)
        elif self._backup_text:
            mime.setText(self._backup_text)
            if self._backup_urls:
                mime.setUrls(self._backup_urls)
            clipboard.setMimeData(mime)

    def clear(self):
        self._backup_text = None
        self._backup_image = None
        self._backup_urls = None
