#!/usr/bin/env python3
"""
CyberClip — Clipboard image capture diagnostic & unit test.
Tests every code path used by clipboard_monitor._process_clipboard for images.
Run AFTER taking a Win+Shift+S screenshot, OR rely on the built-in synthetic test.

Usage:
    python test_clipboard_diag.py            # synthetic test only
    python test_clipboard_diag.py --live     # also read current clipboard
"""
import ctypes
import sys
import hashlib
import io
import time
import traceback

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

CF_BITMAP = 2
CF_DIB    = 8
CF_DIBV5  = 17
GMEM_MOVEABLE = 0x0002

_CF_PNG  = _user32.RegisterClipboardFormatW("PNG")
_CF_JFIF = _user32.RegisterClipboardFormatW("JFIF")

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"
SKIP = "[SKIP]"

results = []

def record(tag, msg):
    line = f"{tag} {msg}"
    print(line)
    results.append(line)

# ── Helpers ───────────────────────────────────────────────────────────────────
def open_clipboard(retries=5, delay=0.05):
    for _ in range(retries):
        if _user32.OpenClipboard(None):
            return True
        time.sleep(delay)
    return False

def close_clipboard():
    try: _user32.CloseClipboard()
    except Exception: pass

def read_fmt_bytes(fmt):
    """Exactly mirrors clipboard_monitor._read_clipboard_format_bytes."""
    if not fmt or not _user32.IsClipboardFormatAvailable(fmt):
        return None
    if not open_clipboard():
        return None
    try:
        h = _user32.GetClipboardData(fmt)
        if not h:
            return None
        p = _kernel32.GlobalLock(h)
        if not p:
            return None
        try:
            size = _kernel32.GlobalSize(h)
            if size <= 0:
                return None
            return bytes((ctypes.c_char * size).from_address(p))
        finally:
            _kernel32.GlobalUnlock(h)
    except Exception as e:
        record(FAIL, f"read_fmt_bytes({fmt}) exception: {e}")
        return None
    finally:
        close_clipboard()

def enumerate_clipboard_formats():
    """Return list of (fmt_id, name) for all formats currently on clipboard."""
    fmts = []
    if not open_clipboard():
        return fmts
    try:
        fmt = 0
        while True:
            fmt = _user32.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            buf = ctypes.create_unicode_buffer(256)
            n = _user32.GetClipboardFormatNameW(fmt, buf, 256)
            name = buf.value if n > 0 else f"<standard>"
            fmts.append((fmt, name))
    finally:
        close_clipboard()
    return fmts

def put_png_on_clipboard(png_bytes):
    """Place raw PNG bytes on clipboard as registered 'PNG' format (like Win+Shift+S)."""
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(png_bytes))
    if not h:
        return False
    p = _kernel32.GlobalLock(h)
    if not p:
        _kernel32.GlobalFree(h)
        return False
    ctypes.memmove(p, png_bytes, len(png_bytes))
    _kernel32.GlobalUnlock(h)

    if not open_clipboard():
        _kernel32.GlobalFree(h)
        return False
    _user32.EmptyClipboard()
    result = _user32.SetClipboardData(_CF_PNG, h)
    close_clipboard()
    return bool(result)

# ── Test suite ────────────────────────────────────────────────────────────────
def test_registration():
    record(INFO, f"CF_PNG  format ID = {_CF_PNG}  (should be > 0xC000)")
    record(INFO, f"CF_JFIF format ID = {_CF_JFIF} (should be > 0xC000)")
    if _CF_PNG > 0xC000:
        record(PASS, "RegisterClipboardFormatW('PNG') succeeded")
    else:
        record(FAIL, "RegisterClipboardFormatW('PNG') returned invalid ID — will break Win+Shift+S capture")
    if _CF_JFIF > 0xC000:
        record(PASS, "RegisterClipboardFormatW('JFIF') succeeded")
    else:
        record(FAIL, "RegisterClipboardFormatW('JFIF') returned invalid ID")

def test_handle_sizes():
    """Verify ctypes can represent a full 64-bit handle value without truncation."""
    record(INFO, "Checking pointer size (must be 8 bytes on 64-bit Windows)")
    import struct
    ptr_size = struct.calcsize("P")
    if ptr_size == 8:
        record(PASS, f"Pointer size = {ptr_size} bytes (64-bit)")
    else:
        record(FAIL, f"Pointer size = {ptr_size} bytes — running 32-bit Python on 64-bit OS?")

    record(INFO, "Verifying c_void_p does not truncate a 40-bit value")
    test_val = 0x1_0000_ABCD
    v = ctypes.c_void_p(test_val)
    if v.value == test_val:
        record(PASS, "c_void_p preserves 40-bit value correctly")
    else:
        record(FAIL, f"c_void_p truncated: expected {hex(test_val)}, got {hex(v.value or 0)}")

def test_synthetic_png():
    """Put a 50x50 red PNG on clipboard via registered 'PNG' format, then read it back."""
    record(INFO, "=== Synthetic PNG test (50x50 red square) ===")

    try:
        from PIL import Image as PILImage
    except ImportError:
        record(SKIP, "Pillow not installed — skipping synthetic test")
        return

    # Build PNG bytes
    img = PILImage.new("RGB", (50, 50), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png_bytes = buf.getvalue()
    record(INFO, f"  Generated PNG: {len(png_bytes)} bytes, magic={png_bytes[:8].hex()}")

    # Place on clipboard
    if _CF_PNG == 0:
        record(FAIL, "  Cannot place PNG — _CF_PNG is 0")
        return
    if not put_png_on_clipboard(png_bytes):
        record(FAIL, "  put_png_on_clipboard() failed")
        return
    record(INFO, "  Placed PNG on clipboard as registered 'PNG' format")
    time.sleep(0.05)

    # Check IsClipboardFormatAvailable
    avail = _user32.IsClipboardFormatAvailable(_CF_PNG)
    if avail:
        record(PASS, f"  IsClipboardFormatAvailable(PNG={_CF_PNG}) = True")
    else:
        record(FAIL, f"  IsClipboardFormatAvailable(PNG={_CF_PNG}) = False after placing data")
        return

    # Enumerate formats
    fmts = enumerate_clipboard_formats()
    record(INFO, f"  Clipboard formats after put: {fmts}")

    # Read back
    raw = read_fmt_bytes(_CF_PNG)
    if raw is None:
        record(FAIL, "  read_fmt_bytes(_CF_PNG) returned None")
        return
    record(PASS, f"  read_fmt_bytes returned {len(raw)} bytes, magic={raw[:8].hex()}")

    # Decode PNG
    try:
        decoded = PILImage.open(io.BytesIO(raw))
        if decoded.width == 50 and decoded.height == 50:
            record(PASS, f"  Decoded correctly: {decoded.width}x{decoded.height} {decoded.mode}")
        else:
            record(FAIL, f"  Decoded wrong size: {decoded.width}x{decoded.height}")
    except Exception as e:
        record(FAIL, f"  PIL.Image.open failed: {e}")

    # Test PIL ImageGrab on our synthetic clipboard
    try:
        from PIL import ImageGrab
        pil = ImageGrab.grabclipboard()
        if pil is None:
            record(INFO, "  PIL ImageGrab.grabclipboard() returned None (PNG-only clipboard, expected)")
        elif isinstance(pil, PILImage.Image):
            record(PASS, f"  PIL ImageGrab: {pil.width}x{pil.height}")
        else:
            record(INFO, f"  PIL ImageGrab returned: {type(pil)}")
    except Exception as e:
        record(INFO, f"  PIL ImageGrab exception: {e}")

    # Test Qt clipboard
    try:
        app = _get_qt_app()
        clipboard = app.clipboard()
        mime = clipboard.mimeData()
        has_img = mime.hasImage()
        qt_img  = clipboard.image()
        record(INFO, f"  Qt mime.hasImage()={has_img}, clipboard.image().isNull()={qt_img.isNull()}")
        if has_img and not qt_img.isNull():
            record(PASS, f"  Qt clipboard.image(): {qt_img.width()}x{qt_img.height()}")
        elif has_img:
            record(INFO, "  Qt hasImage=True but image is null (Qt can't decode raw PNG format — OK, use Win32 path)")
        else:
            record(INFO, "  Qt hasImage=False for raw PNG format — our Win32 fallback is essential")
    except Exception as e:
        record(INFO, f"  Qt test skipped: {e}")

_qt_app = None
def _get_qt_app():
    global _qt_app
    if _qt_app is None:
        from PyQt6.QtWidgets import QApplication
        _qt_app = QApplication.instance() or QApplication(sys.argv)
    return _qt_app

def test_live_clipboard():
    """Test reading whatever is currently on the clipboard."""
    record(INFO, "=== Live clipboard test ===")
    fmts = enumerate_clipboard_formats()
    if not fmts:
        record(INFO, "  Clipboard appears empty or unreadable")
        return
    record(INFO, f"  Current clipboard formats:")
    for fid, fname in fmts:
        marker = " <-- PNG!" if fid == _CF_PNG else (" <-- DIB" if fid in (CF_DIB, CF_DIBV5) else "")
        record(INFO, f"    {fid:5d}: {fname}{marker}")

    # Check if PNG format is available
    if _user32.IsClipboardFormatAvailable(_CF_PNG):
        record(INFO, f"  PNG format ({_CF_PNG}) is AVAILABLE")
        raw = read_fmt_bytes(_CF_PNG)
        if raw:
            record(PASS, f"  read_fmt_bytes(PNG): {len(raw)} bytes, magic={raw[:8].hex()}")
            try:
                from PIL import Image as PILImage
                img = PILImage.open(io.BytesIO(raw))
                record(PASS, f"  Decoded: {img.width}x{img.height} {img.mode}")
            except Exception as e:
                record(FAIL, f"  PIL decode error: {e}")
        else:
            record(FAIL, f"  read_fmt_bytes(PNG) returned None despite format being available")
    else:
        record(INFO, "  PNG registered format NOT on clipboard (not a Win+Shift+S screenshot)")

    for fmt_id, fmt_name in [(CF_DIB, "CF_DIB"), (CF_DIBV5, "CF_DIBV5"), (CF_BITMAP, "CF_BITMAP")]:
        if _user32.IsClipboardFormatAvailable(fmt_id):
            record(INFO, f"  {fmt_name} available — PIL ImageGrab should work")
            try:
                from PIL import ImageGrab
                pil = ImageGrab.grabclipboard()
                if isinstance(pil, __import__('PIL').Image.Image):
                    record(PASS, f"  PIL ImageGrab: {pil.width}x{pil.height}")
                else:
                    record(INFO, f"  PIL ImageGrab returned: {pil!r}")
            except Exception as e:
                record(FAIL, f"  PIL ImageGrab error: {e}")
            break

def test_full_pipeline():
    """Run the exact same logic as clipboard_monitor._process_clipboard on synthetic data."""
    record(INFO, "=== Full pipeline simulation (synthetic 80x80 blue PNG) ===")
    try:
        from PIL import Image as PILImage
    except ImportError:
        record(SKIP, "Pillow not installed")
        return

    img = PILImage.new("RGB", (80, 80), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    png_bytes = buf.getvalue()

    if not put_png_on_clipboard(png_bytes):
        record(FAIL, "Cannot put PNG on clipboard")
        return
    time.sleep(0.05)

    # Mirror the logic from _process_clipboard exactly
    captured = None

    # Check has_image (same OR logic)
    try:
        from PyQt6.QtWidgets import QApplication
        app = _get_qt_app()
        clipboard = app.clipboard()
        mime = clipboard.mimeData()
        has_image = mime.hasImage() or any(
            _user32.IsClipboardFormatAvailable(f)
            for f in (CF_DIBV5, CF_DIB, CF_BITMAP, _CF_PNG, _CF_JFIF) if f
        )
        record(INFO if has_image else FAIL, f"  has_image={has_image}")
    except Exception as e:
        record(INFO, f"  Qt unavailable, using Win32 only: {e}")
        has_image = any(
            _user32.IsClipboardFormatAvailable(f)
            for f in (CF_DIBV5, CF_DIB, CF_BITMAP, _CF_PNG, _CF_JFIF) if f
        )

    if not has_image:
        record(FAIL, "  Pipeline: has_image=False, image would be missed entirely")
        return

    # Attempt 1: Qt image
    try:
        app = _get_qt_app()
        qt_img = app.clipboard().image()
        if not qt_img.isNull() and qt_img.width() > 0:
            record(PASS, f"  Attempt 1 (Qt): {qt_img.width()}x{qt_img.height()}")
            captured = "qt"
        else:
            record(INFO, "  Attempt 1 (Qt): null image (expected for raw PNG format)")
    except Exception as e:
        record(INFO, f"  Attempt 1 (Qt) error: {e}")

    if not captured:
        # Attempt 2: PIL ImageGrab
        try:
            from PIL import ImageGrab
            pil_img = ImageGrab.grabclipboard()
            if isinstance(pil_img, PILImage.Image):
                record(PASS, f"  Attempt 2 (PIL): {pil_img.width}x{pil_img.height}")
                captured = "pil"
            else:
                record(INFO, f"  Attempt 2 (PIL): returned {pil_img!r} (expected None for PNG-only)")
        except Exception as e:
            record(INFO, f"  Attempt 2 (PIL) error: {e}")

    if not captured:
        # Attempt 3: Win32 registered format
        for raw_fmt, name in [(_CF_PNG, "PNG"), (_CF_JFIF, "JFIF")]:
            raw = read_fmt_bytes(raw_fmt)
            if not raw:
                continue
            try:
                decoded = PILImage.open(io.BytesIO(raw))
                record(PASS, f"  Attempt 3 (Win32/{name}): {decoded.width}x{decoded.height} — WOULD SAVE")
                captured = f"win32_{name}"
                break
            except Exception as e:
                record(FAIL, f"  Attempt 3 Win32/{name} decode error: {e}")

    if captured:
        record(PASS, f"Pipeline SUCCESS via: {captured}")
    else:
        record(FAIL, "Pipeline FAILED — all 3 attempts returned nothing. Image would NOT be captured.")

# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    live = "--live" in sys.argv
    print("=" * 60)
    print("CyberClip Clipboard Image Diagnostic")
    print("=" * 60)

    test_registration()
    print()
    test_handle_sizes()
    print()
    test_synthetic_png()
    print()
    test_full_pipeline()

    if live:
        print()
        test_live_clipboard()

    print()
    print("=" * 60)
    passes  = sum(1 for r in results if r.startswith(PASS))
    fails   = sum(1 for r in results if r.startswith(FAIL))
    print(f"SUMMARY: {passes} passed, {fails} failed")
    print("=" * 60)
    sys.exit(0 if fails == 0 else 1)
