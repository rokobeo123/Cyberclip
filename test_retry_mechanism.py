"""Test retry mechanism for delayed-rendering clipboard sources (e.g., Snipping Tool)."""
import sys, ctypes, io, time
sys.path.insert(0, '.')

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_kernel32.GlobalAlloc.restype = ctypes.c_void_p
_kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
_kernel32.GlobalUnlock.restype = ctypes.c_bool
_kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
_user32.SetClipboardData.restype = ctypes.c_void_p
_user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
_user32.GetClipboardData.restype = ctypes.c_void_p
_user32.GetClipboardData.argtypes = [ctypes.c_uint]
_kernel32.GlobalSize.restype = ctypes.c_size_t
_kernel32.GlobalSize.argtypes = [ctypes.c_void_p]
_CF_PNG = _user32.RegisterClipboardFormatW("PNG")
GMEM_MOVEABLE = 0x0002

from PIL import Image as PILImage
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from cyberclip.core.clipboard_monitor import ClipboardMonitor

app = QApplication.instance() or QApplication(sys.argv)

class FakeStore:
    def __init__(self): self.saved = []
    def save_image(self, data, fmt="PNG"):
        path = f"fake_{len(self.saved)}.png"
        self.saved.append(path)
        print(f"[INFO] save_image: {len(data)} bytes -> {path}")
        return path
    def save_qimage(self, qi):
        from PyQt6.QtCore import QBuffer, QIODevice
        buf = QBuffer(); buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qi.save(buf, "PNG"); data = bytes(buf.data()); buf.close()
        return self.save_image(data)
    def cleanup_orphans(self, db=None): pass

store = FakeStore()
monitor = ClipboardMonitor(image_store=store)
captured = []
monitor.item_captured.connect(lambda item: captured.append(item))

def place_png():
    """Place the actual PNG 600ms after the sequence number changed (delayed render)."""
    img = PILImage.new("RGB", (40, 40), (0, 200, 100))
    buf = io.BytesIO(); img.save(buf, "PNG"); png = buf.getvalue()
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(png))
    p = _kernel32.GlobalLock(h); ctypes.memmove(p, png, len(png)); _kernel32.GlobalUnlock(h)
    for _ in range(5):
        if _user32.OpenClipboard(None): break
        time.sleep(0.05)
    _user32.EmptyClipboard(); _user32.SetClipboardData(_CF_PNG, h); _user32.CloseClipboard()
    print("[INFO] PNG placed on clipboard (600ms delayed)")

def initial_change():
    """Bump sequence number but leave clipboard empty (like delayed render init)."""
    for _ in range(5):
        if _user32.OpenClipboard(None): break
        time.sleep(0.05)
    _user32.EmptyClipboard(); _user32.CloseClipboard()
    print("[INFO] Seq bumped, clipboard empty (delayed render simulation)")

QTimer.singleShot(200, initial_change)   # triggers monitor detection, no data
QTimer.singleShot(800, place_png)        # data appears 600ms later
QTimer.singleShot(2000, app.quit)        # quit after giving retry time to fire

app.exec()
monitor.stop()

if captured:
    print(f"[PASS] Retry works: {len(captured)} item(s) captured -> {captured[0].text_content}")
    sys.exit(0)
else:
    print("[FAIL] Retry FAILED: no items captured within 2000ms")
    sys.exit(1)
