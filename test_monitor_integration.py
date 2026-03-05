#!/usr/bin/env python3
"""
CyberClip — ClipboardMonitor integration test.
Creates a real ClipboardMonitor, puts synthetic images on clipboard via Win32,
and verifies the item_captured signal fires within a reasonable timeout.

Usage: python test_monitor_integration.py
"""
import sys
import os
import ctypes
import hashlib
import io
import time

# ── Python path ───────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

# ── Win32 setup ──────────────────────────────────────────────────────────────
_user32   = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.GetClipboardData.restype    = ctypes.c_void_p
_user32.GetClipboardData.argtypes   = [ctypes.c_uint]
_user32.SetClipboardData.restype    = ctypes.c_void_p
_user32.SetClipboardData.argtypes   = [ctypes.c_uint, ctypes.c_void_p]
_kernel32.GlobalAlloc.restype       = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes      = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype        = ctypes.c_void_p
_kernel32.GlobalLock.argtypes       = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype      = ctypes.c_bool
_kernel32.GlobalUnlock.argtypes     = [ctypes.c_void_p]
_kernel32.GlobalSize.restype        = ctypes.c_size_t
_kernel32.GlobalSize.argtypes       = [ctypes.c_void_p]
_kernel32.GlobalFree.restype        = ctypes.c_void_p
_kernel32.GlobalFree.argtypes       = [ctypes.c_void_p]

CF_BITMAP = 2; CF_DIB = 8; CF_DIBV5 = 17
GMEM_MOVEABLE = 0x0002

_CF_PNG  = _user32.RegisterClipboardFormatW("PNG")
_CF_JFIF = _user32.RegisterClipboardFormatW("JFIF")

PASS = "[PASS]"; FAIL = "[FAIL]"; INFO = "[INFO]"; WARN = "[WARN]"
results = []
def log(tag, msg):
    line = f"{tag} {msg}"; print(line); results.append(line)

# ── Clipboard helpers ─────────────────────────────────────────────────────────
def put_png_on_clipboard(png_bytes, fmt=None):
    if fmt is None: fmt = _CF_PNG
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(png_bytes))
    if not h: return False
    p = _kernel32.GlobalLock(h)
    if not p: _kernel32.GlobalFree(h); return False
    ctypes.memmove(p, png_bytes, len(png_bytes))
    _kernel32.GlobalUnlock(h)
    for _ in range(5):
        if _user32.OpenClipboard(None): break
        time.sleep(0.05)
    else:
        return False
    _user32.EmptyClipboard()
    result = _user32.SetClipboardData(fmt, h)
    _user32.CloseClipboard()
    return bool(result)

def put_dib_on_clipboard(png_bytes):
    """Convert PNG to CF_DIB (BITMAPINFOHEADER + pixels) and put on clipboard."""
    from PIL import Image as PILImage
    img = PILImage.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    pixels = img.tobytes()
    # Build BITMAPINFOHEADER (40 bytes)
    import struct
    biSize = 40; biBitCount = 24; biCompression = 0
    biSizeImage = len(pixels); biXPelsPerMeter = 0; biYPelsPerMeter = 0
    biClrUsed = 0; biClrImportant = 0
    stride = ((w * 3 + 3) & ~3)
    header = struct.pack("<IiiHHIIiiII",
        biSize, w, -h, 1, biBitCount, biCompression,
        biSizeImage, biXPelsPerMeter, biYPelsPerMeter, biClrUsed, biClrImportant)
    dib = header + pixels

    h_mem = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib))
    if not h_mem: return False
    p = _kernel32.GlobalLock(h_mem)
    if not p: return False
    ctypes.memmove(p, dib, len(dib))
    _kernel32.GlobalUnlock(h_mem)
    for _ in range(5):
        if _user32.OpenClipboard(None): break
        time.sleep(0.05)
    else: return False
    _user32.EmptyClipboard()
    result = _user32.SetClipboardData(CF_DIB, h_mem)
    _user32.CloseClipboard()
    return bool(result)

def put_both_on_clipboard(png_bytes):
    """Put BOTH registered PNG format AND CF_DIB on clipboard (mirrors Win+Shift+S exactly)."""
    from PIL import Image as PILImage
    img = PILImage.open(io.BytesIO(png_bytes)).convert("RGB")
    w, h_px = img.size
    pixels = img.tobytes()
    import struct
    header = struct.pack("<IiiHHIIiiII",
        40, w, -h_px, 1, 24, 0, len(pixels), 0, 0, 0, 0)
    dib = header + pixels

    # Alloc both
    h_png = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(png_bytes))
    if not h_png: return False
    p = _kernel32.GlobalLock(h_png)
    ctypes.memmove(p, png_bytes, len(png_bytes))
    _kernel32.GlobalUnlock(h_png)

    h_dib = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(dib))
    if not h_dib: return False
    p = _kernel32.GlobalLock(h_dib)
    ctypes.memmove(p, dib, len(dib))
    _kernel32.GlobalUnlock(h_dib)

    for _ in range(5):
        if _user32.OpenClipboard(None): break
        time.sleep(0.05)
    else: return False
    _user32.EmptyClipboard()
    _user32.SetClipboardData(_CF_PNG, h_png)
    _user32.SetClipboardData(CF_DIB, h_dib)
    _user32.CloseClipboard()
    return True

# ── Fake ImageStore ───────────────────────────────────────────────────────────
class FakeImageStore:
    def __init__(self):
        self.saved = []
    def save_image(self, data, fmt="PNG"):
        path = f"fake_img_{len(self.saved)}_{hashlib.md5(data).hexdigest()[:8]}.png"
        self.saved.append(path)
        log(INFO, f"  ImageStore.save_image called: {len(data)} bytes → {path}")
        return path
    def save_qimage(self, qimg):
        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg.save(buf, "PNG")
        data = bytes(buf.data())
        buf.close()
        return self.save_image(data)
    def cleanup_orphans(self, db=None): pass

# ── Monitor integration test ──────────────────────────────────────────────────
def run_monitor_test(label, clipboard_put_fn, expected_type="image", timeout_ms=1000):
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from cyberclip.core.clipboard_monitor import ClipboardMonitor
    from cyberclip.utils.constants import TYPE_IMAGE

    app = QApplication.instance() or QApplication(sys.argv)

    store = FakeImageStore()
    monitor = ClipboardMonitor(image_store=store)

    captured_items = []
    monitor.item_captured.connect(lambda item: captured_items.append(item))

    # Small delay to let monitor init, then put clipboard data
    def do_put():
        ok = clipboard_put_fn()
        if not ok:
            log(FAIL, f"  {label}: clipboard_put_fn() failed")
            QTimer.singleShot(timeout_ms, app.quit)
        else:
            log(INFO, f"  {label}: clipboard data placed, waiting {timeout_ms}ms...")
            QTimer.singleShot(timeout_ms, app.quit)

    QTimer.singleShot(200, do_put)
    app.exec()
    monitor.stop()

    if captured_items:
        item = captured_items[0]
        if item.content_type == TYPE_IMAGE:
            log(PASS, f"{label}: captured image item → {item.text_content}")
        else:
            log(WARN, f"{label}: captured {item.content_type} item (expected image)")
        return True
    else:
        log(FAIL, f"{label}: NO item captured within {timeout_ms}ms")
        return False

# ── Tests ─────────────────────────────────────────────────────────────────────
def make_png(color=(255, 0, 0), size=(60, 60)):
    from PIL import Image as PILImage
    img = PILImage.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

def test_qt_image_is_readable():
    """Verify Qt clipboard.image() works for each format type."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from PIL import Image as PILImage

    png = make_png((0, 255, 0), (70, 70))

    log(INFO, "=== T1: Qt reads PNG-only clipboard ===")
    put_png_on_clipboard(png, _CF_PNG)
    time.sleep(0.1)
    clipboard = app.clipboard()
    mime = clipboard.mimeData()
    img = clipboard.image()
    log(INFO if img.isNull() else PASS,
        f"  Qt hasImage={mime.hasImage()}, image null={img.isNull()}" +
        (f", size={img.width()}x{img.height()}" if not img.isNull() else ""))

    log(INFO, "=== T2: Qt reads CF_DIB-only clipboard ===")
    put_dib_on_clipboard(png)
    time.sleep(0.1)
    mime = clipboard.mimeData()
    img = clipboard.image()
    log(INFO if img.isNull() else PASS,
        f"  Qt hasImage={mime.hasImage()}, image null={img.isNull()}" +
        (f", size={img.width()}x{img.height()}" if not img.isNull() else ""))

    log(INFO, "=== T3: Qt reads PNG+CF_DIB clipboard (Win+Shift+S simulation) ===")
    put_both_on_clipboard(png)
    time.sleep(0.1)
    mime = clipboard.mimeData()
    img = clipboard.image()
    log(INFO if img.isNull() else PASS,
        f"  Qt hasImage={mime.hasImage()}, image null={img.isNull()}" +
        (f", size={img.width()}x{img.height()}" if not img.isNull() else ""))

def test_monitor_png_only():
    """Monitor test: PNG-only clipboard (registered format, no CF_DIB)."""
    log(INFO, "=== Monitor T4: PNG-only (registered format) ===")
    png = make_png((255, 0, 0), (64, 64))
    return run_monitor_test("PNG-only", lambda: put_png_on_clipboard(png, _CF_PNG))

def test_monitor_dib_only():
    """Monitor test: CF_DIB only."""
    log(INFO, "=== Monitor T5: CF_DIB only ===")
    png = make_png((0, 0, 255), (64, 64))
    return run_monitor_test("CF_DIB-only", lambda: put_dib_on_clipboard(png))

def test_monitor_both_formats():
    """Monitor test: PNG + CF_DIB (real Win+Shift+S simulation)."""
    log(INFO, "=== Monitor T6: PNG + CF_DIB (Win+Shift+S simulation) ===")
    png = make_png((128, 0, 255), (64, 64))
    return run_monitor_test("PNG+CF_DIB", lambda: put_both_on_clipboard(png))

def test_pil_format_compatibility():
    """Test PIL ImageGrab on each clipboard type."""
    from PIL import ImageGrab, Image as PILImage
    log(INFO, "=== T7: PIL ImageGrab compatibility ===")

    for label, put_fn in [
        ("PNG-only",    lambda: put_png_on_clipboard(make_png((255, 255, 0)), _CF_PNG)),
        ("CF_DIB-only", lambda: put_dib_on_clipboard(make_png((0, 255, 255)))),
        ("PNG+CF_DIB",  lambda: put_both_on_clipboard(make_png((255, 0, 255)))),
    ]:
        put_fn()
        time.sleep(0.1)
        try:
            result = ImageGrab.grabclipboard()
            if isinstance(result, PILImage.Image):
                log(PASS, f"  PIL/{label}: {result.width}x{result.height}")
            else:
                log(INFO, f"  PIL/{label}: returned {result!r}")
        except Exception as e:
            log(FAIL, f"  PIL/{label}: exception: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 65)
    print("CyberClip — ClipboardMonitor Integration Tests")
    print("=" * 65)

    try:
        from PIL import Image as PILImage
    except ImportError:
        print(f"{FAIL} Pillow not installed — run: pip install Pillow")
        sys.exit(1)

    test_qt_image_is_readable()
    print()
    test_pil_format_compatibility()
    print()
    t4 = test_monitor_png_only()
    print()
    t5 = test_monitor_dib_only()
    print()
    t6 = test_monitor_both_formats()

    print()
    print("=" * 65)
    passes = sum(1 for r in results if r.startswith(PASS))
    fails  = sum(1 for r in results if r.startswith(FAIL))
    warns  = sum(1 for r in results if r.startswith(WARN))
    print(f"SUMMARY: {passes} passed, {fails} failed, {warns} warnings")
    print("=" * 65)
    sys.exit(0 if fails == 0 else 1)
