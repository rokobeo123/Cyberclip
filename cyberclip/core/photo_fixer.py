"""Photo fixer - normalizes clipboard images for universal paste compatibility."""
import io
from PIL import Image


def fix_image(image_data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_data))
        # Convert RGBA to RGB with white background for compatibility
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        return buf.getvalue()
    except Exception:
        return image_data


def create_thumbnail(image_data: bytes, max_size: tuple = (120, 80)) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_data))
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        buf = io.BytesIO()
        img.save(buf, "PNG")
        return buf.getvalue()
    except Exception:
        return image_data
