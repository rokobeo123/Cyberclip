"""Win32 API helper wrappers for CyberClip."""
import ctypes
import ctypes.wintypes as wt
from ctypes import windll, byref, sizeof, c_int, POINTER, Structure

user32 = windll.user32
kernel32 = windll.kernel32
shell32 = windll.shell32
dwmapi = ctypes.WinDLL("dwmapi")

# Constants
WM_HOTKEY = 0x0312
WM_CLIPBOARDUPDATE = 0x031D
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x0080
WS_EX_APPWINDOW = 0x40000
WS_EX_NOACTIVATE = 0x08000000

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

# DWM blur constants
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWM_SYSTEMBACKDROP_TYPE = 38
DWMSBT_MAINWINDOW = 2
DWMSBT_TRANSIENTWINDOW = 3
DWMSBT_TABBEDWINDOW = 4


class KEYBDINPUT(Structure):
    _fields_ = [
        ("wVk", wt.WORD),
        ("wScan", wt.WORD),
        ("dwFlags", wt.DWORD),
        ("time", wt.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(Structure):
    _fields_ = [
        ("type", wt.DWORD),
        ("union", INPUT_UNION),
    ]


def send_key(vk=0, scan=0, flags=0):
    """Send a single key event using keybd_event (more compatible than SendInput)."""
    user32.keybd_event(vk, scan, flags, 0)


def release_all_modifiers():
    """Release Ctrl, Shift, Alt to clear stuck keys from global hotkey."""
    for vk in (VK_CONTROL, VK_SHIFT, VK_MENU, 0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def wait_for_modifiers_release(timeout_ms=2000):
    """Wait until the user physically releases all modifier keys."""
    import time
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        ctrl = user32.GetAsyncKeyState(VK_CONTROL) & 0x8000
        shift = user32.GetAsyncKeyState(VK_SHIFT) & 0x8000
        alt = user32.GetAsyncKeyState(VK_MENU) & 0x8000
        if not (ctrl or shift or alt):
            return True
        time.sleep(0.01)
    return False


def send_ctrl_v():
    """Send Ctrl+V keystroke reliably.
    Waits for the user to release modifier keys first, so holding
    Ctrl+Shift and repeatedly pressing V works correctly."""
    import time
    wait_for_modifiers_release(timeout_ms=1500)
    time.sleep(0.02)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(0x56, 0, 0, 0)  # V down
    time.sleep(0.02)
    user32.keybd_event(0x56, 0, KEYEVENTF_KEYUP, 0)  # V up
    time.sleep(0.02)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def get_foreground_hwnd():
    """Return the current foreground window handle."""
    return user32.GetForegroundWindow()


def set_foreground(hwnd):
    """Bring a window to foreground (best-effort)."""
    try:
        current_thread = kernel32.GetCurrentThreadId()
        fg_thread = user32.GetWindowThreadProcessId(
            user32.GetForegroundWindow(), None
        )
        if current_thread != fg_thread:
            user32.AttachThreadInput(current_thread, fg_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        if current_thread != fg_thread:
            user32.AttachThreadInput(current_thread, fg_thread, False)
    except Exception:
        user32.SetForegroundWindow(hwnd)


def send_unicode_char(char):
    scan = ord(char)
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.union.ki.wVk = 0
    inp_down.union.ki.wScan = scan
    inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE
    inp_down.union.ki.time = 0
    inp_down.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.union.ki.wVk = 0
    inp_up.union.ki.wScan = scan
    inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
    inp_up.union.ki.time = 0
    inp_up.union.ki.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))

    arr = (INPUT * 2)(inp_down, inp_up)
    user32.SendInput(2, byref(arr), sizeof(INPUT))


def get_foreground_window_info():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None, None, None

    # Window title
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # Process name
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, byref(pid))
    try:
        import psutil
        proc = psutil.Process(pid.value)
        exe_name = proc.name()
    except Exception:
        exe_name = ""

    return hwnd, title, exe_name


def set_window_topmost(hwnd, topmost=True):
    flag = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    user32.SetWindowPos(
        hwnd, flag, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
    )


def register_hotkey(hwnd, id_, modifiers, vk):
    return user32.RegisterHotKey(hwnd, id_, modifiers | MOD_NOREPEAT, vk)


def unregister_hotkey(hwnd, id_):
    return user32.UnregisterHotKey(hwnd, id_)


def add_clipboard_listener(hwnd):
    return user32.AddClipboardFormatListener(hwnd)


def remove_clipboard_listener(hwnd):
    return user32.RemoveClipboardFormatListener(hwnd)


def enable_blur(hwnd_int):
    try:
        val = c_int(1)
        dwmapi.DwmSetWindowAttribute(
            hwnd_int, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(val), sizeof(val)
        )
        val2 = c_int(DWMSBT_TRANSIENTWINDOW)
        dwmapi.DwmSetWindowAttribute(
            hwnd_int, DWM_SYSTEMBACKDROP_TYPE, byref(val2), sizeof(val2)
        )
    except Exception:
        pass
