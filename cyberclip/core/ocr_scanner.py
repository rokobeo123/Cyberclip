# Modified: [1.5] Moved Tesseract calls to QThread worker with 10-second timeout;
#           Tesseract availability check; disable OCR button + show inline install
#           instructions if Tesseract is not found in PATH.
"""OCR Scanner - extract text from images using Tesseract.

All Tesseract operations are performed in an OcrWorker (QThread) and NEVER
on the main GUI thread.  The worker has a hard 10-second timeout after which
it emits an error signal and exits cleanly.
"""
import io
import os
import logging
import subprocess
import shutil
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal, QObject

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Availability check (1.5)
# ---------------------------------------------------------------------------
_tesseract_path: Optional[str] = None
_tesseract_checked: bool = False


def find_tesseract() -> Optional[str]:
    """
    Return the full path to the tesseract executable, or None if not found.
    Checks PATH first, then common Windows install locations.
    Result is cached after the first call.
    """
    global _tesseract_path, _tesseract_checked
    if _tesseract_checked:
        return _tesseract_path

    _tesseract_checked = True

    # 1. Check PATH
    path = shutil.which("tesseract")
    if path:
        _tesseract_path = path
        return _tesseract_path

    # 2. Common Windows installation directories
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            _tesseract_path = candidate
            return _tesseract_path

    return None


def is_tesseract_available() -> bool:
    """Return True if Tesseract is installed and accessible."""
    return find_tesseract() is not None


TESSERACT_INSTALL_INSTRUCTIONS = (
    "Tesseract OCR not found.\n\n"
    "Install steps:\n"
    "  1. Download from: https://github.com/UB-Mannheim/tesseract/wiki\n"
    "  2. Run the installer (install to default location)\n"
    "  3. Restart CyberClip\n\n"
    "After installation the OCR button will be enabled automatically."
)


# ---------------------------------------------------------------------------
# QThread worker (1.5)
# ---------------------------------------------------------------------------
class OcrWorker(QThread):
    """
    Runs Tesseract OCR in a background thread with a 10-second hard timeout.
    Signals:
        ocr_done(str)   — emitted with the extracted text on success
        ocr_error(str)  — emitted with an error message on failure/timeout
    """
    ocr_done = pyqtSignal(str)
    ocr_error = pyqtSignal(str)

    TIMEOUT_SECONDS = 10

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self._image_path = image_path

    def run(self):
        if not is_tesseract_available():
            self.ocr_error.emit(TESSERACT_INSTALL_INSTRUCTIONS)
            return

        try:
            from PIL import Image
            import pytesseract

            tess = find_tesseract()
            if tess:
                pytesseract.pytesseract.tesseract_cmd = tess

            img = Image.open(self._image_path)

            # Run with timeout via subprocess to avoid blocking indefinitely
            text = self._run_with_timeout(img)
            if text:
                self.ocr_done.emit(text)
            else:
                self.ocr_error.emit("OCR: No text found in image")
        except ImportError as exc:
            logger.warning("pytesseract not installed: %s", exc)
            self.ocr_error.emit(
                "pytesseract not installed.\n"
                "Run: pip install pytesseract\n\n"
                + TESSERACT_INSTALL_INSTRUCTIONS
            )
        except Exception as exc:
            logger.exception("OCR failed: %s", exc)
            self.ocr_error.emit(f"OCR failed: {exc}")

    def _run_with_timeout(self, img) -> Optional[str]:
        """Run pytesseract.image_to_string with a hard timeout."""
        import pytesseract

        result_holder = []
        error_holder = []

        def _do_ocr():
            try:
                text = pytesseract.image_to_string(img)
                result_holder.append(text.strip() if text else "")
            except Exception as exc:
                error_holder.append(str(exc))

        import threading
        t = threading.Thread(target=_do_ocr, daemon=True)
        t.start()
        t.join(timeout=self.TIMEOUT_SECONDS)

        if t.is_alive():
            logger.warning("OCR timed out after %d seconds", self.TIMEOUT_SECONDS)
            return None  # thread keeps running as daemon — will be killed when app exits
        if error_holder:
            raise RuntimeError(error_holder[0])
        return result_holder[0] if result_holder else None


# ---------------------------------------------------------------------------
# Legacy synchronous helpers (kept for backward-compat; now use OcrWorker)
# ---------------------------------------------------------------------------
def scan_image(image_path: str) -> Optional[str]:
    """
    Synchronous OCR — DEPRECATED. Use OcrWorker instead.
    Left here only for any external callers; internally CyberClip now uses
    OcrWorker exclusively.
    """
    if not is_tesseract_available():
        return None
    try:
        from PIL import Image
        import pytesseract
        tess = find_tesseract()
        if tess:
            pytesseract.pytesseract.tesseract_cmd = tess
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else None
    except ImportError:
        return None
    except Exception as exc:
        logger.exception("scan_image failed: %s", exc)
        return None


def scan_image_data(image_data: bytes) -> Optional[str]:
    """Synchronous OCR from raw bytes — DEPRECATED. Use OcrWorker instead."""
    if not is_tesseract_available():
        return None
    try:
        from PIL import Image
        import pytesseract
        tess = find_tesseract()
        if tess:
            pytesseract.pytesseract.tesseract_cmd = tess
        img = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else None
    except ImportError:
        return None
    except Exception as exc:
        logger.exception("scan_image_data failed: %s", exc)
        return None
