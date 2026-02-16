"""Hidden folder image storage for clipboard images."""
import os
import hashlib
import time
from typing import Optional

from PIL import Image
import io

from cyberclip.utils.constants import IMAGE_STORE_DIR


class ImageStore:
    def __init__(self):
        os.makedirs(IMAGE_STORE_DIR, exist_ok=True)
        # Set hidden attribute on Windows
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(IMAGE_STORE_DIR, 0x02)
        except Exception:
            pass

    def save_image(self, image_data: bytes, fmt: str = "PNG") -> str:
        h = hashlib.md5(image_data).hexdigest()[:12]
        ts = str(int(time.time() * 1000))
        filename = f"clip_{ts}_{h}.png"
        filepath = os.path.join(IMAGE_STORE_DIR, filename)

        # Normalize to PNG for universal compatibility
        try:
            img = Image.open(io.BytesIO(image_data))
            if img.mode == "RGBA":
                bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                img = bg
            img.save(filepath, "PNG", optimize=True)
        except Exception:
            with open(filepath, "wb") as f:
                f.write(image_data)

        return filepath

    def save_qimage(self, qimage) -> str:
        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimage.save(buf, "PNG")
        data = bytes(buf.data())
        buf.close()
        return self.save_image(data)

    def load_image(self, filepath: str) -> Optional[bytes]:
        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                return f.read()
        return None

    def delete_image(self, filepath: str):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

    def cleanup_orphans(self, valid_paths: set):
        for f in os.listdir(IMAGE_STORE_DIR):
            fp = os.path.join(IMAGE_STORE_DIR, f)
            if fp not in valid_paths:
                try:
                    os.remove(fp)
                except Exception:
                    pass

    def get_thumbnail(self, filepath: str, size: tuple = (80, 80)) -> Optional[bytes]:
        try:
            img = Image.open(filepath)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
        except Exception:
            return None
