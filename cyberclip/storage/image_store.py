# Modified: [1.7] cleanup_orphans() now compares disk files against DB paths;
#           delete_image() improved; startup_cleanup() entry point for app.py
"""Hidden folder image storage for clipboard images."""
import logging
import os
import hashlib
import time
from typing import Optional

from PIL import Image
import io

from cyberclip.utils.constants import IMAGE_STORE_DIR

logger = logging.getLogger(__name__)


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
            try:
                with open(filepath, "rb") as f:
                    return f.read()
            except OSError as exc:
                logger.warning("load_image failed for %s: %s", filepath, exc)
        return None

    def delete_image(self, filepath: str):
        try:
            if filepath and os.path.exists(filepath):
                os.remove(filepath)
        except OSError as exc:
            logger.warning("delete_image failed for %s: %s", filepath, exc)

    # ── 1.7 Orphan cleanup ────────────────────────────────────────────────
    def cleanup_orphans(self, valid_paths: set):
        """
        Delete any image files in IMAGE_STORE_DIR that are NOT in *valid_paths*.
        Called at startup with the set of image_path values from the database.
        """
        if not os.path.isdir(IMAGE_STORE_DIR):
            return
        removed = 0
        for filename in os.listdir(IMAGE_STORE_DIR):
            fp = os.path.join(IMAGE_STORE_DIR, filename)
            if not os.path.isfile(fp):
                continue
            if fp not in valid_paths:
                try:
                    os.remove(fp)
                    removed += 1
                except OSError as exc:
                    logger.warning("cleanup_orphans: could not remove %s: %s", fp, exc)
        if removed:
            logger.info("cleanup_orphans: removed %d orphaned image file(s)", removed)

    def startup_cleanup(self, db) -> int:
        """
        1.7 — Compare image files on disk against DB references and delete orphans.
        *db* must be a Database instance that exposes get_all_image_paths().
        Returns number of orphan files removed.
        """
        try:
            valid_paths = db.get_all_image_paths()
        except Exception as exc:
            logger.error("startup_cleanup: could not fetch image paths from DB: %s", exc)
            return 0
        if not os.path.isdir(IMAGE_STORE_DIR):
            return 0
        removed = 0
        for filename in os.listdir(IMAGE_STORE_DIR):
            fp = os.path.join(IMAGE_STORE_DIR, filename)
            if not os.path.isfile(fp):
                continue
            if fp not in valid_paths:
                try:
                    os.remove(fp)
                    removed += 1
                except OSError as exc:
                    logger.warning("startup_cleanup: could not remove %s: %s", fp, exc)
        if removed:
            logger.info("startup_cleanup: removed %d orphaned image(s)", removed)
        return removed

    # ── Thumbnail helpers ─────────────────────────────────────────────────
    def get_thumbnail(self, filepath: str, size: tuple = (80, 80)) -> Optional[bytes]:
        try:
            img = Image.open(filepath)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, "PNG")
            return buf.getvalue()
        except Exception as exc:
            logger.debug("get_thumbnail failed for %s: %s", filepath, exc)
            return None
