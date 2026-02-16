"""OCR Scanner - extract text from images using Tesseract."""
import io
from typing import Optional
from PIL import Image


def scan_image(image_path: str) -> Optional[str]:
    try:
        import pytesseract
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else None
    except ImportError:
        return None
    except Exception:
        return None


def scan_image_data(image_data: bytes) -> Optional[str]:
    try:
        import pytesseract
        img = Image.open(io.BytesIO(image_data))
        text = pytesseract.image_to_string(img)
        return text.strip() if text.strip() else None
    except ImportError:
        return None
    except Exception:
        return None
