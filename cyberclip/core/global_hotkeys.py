# Modified: [1.4] RegisterHotKey failure notification with user-visible tray message;
#           hotkey conflict detection; thread-safety note on registration
"""Lightweight global hotkey manager using Win32 RegisterHotKey.

Registers system-wide hotkeys that work even when the app window is hidden.
User can customize all hotkeys from Settings.

THREAD SAFETY:  RegisterHotKey / UnregisterHotKey MUST be called from the
same thread that processes the Win32 message loop.  In CyberClip the
GlobalHotkeyManager is constructed on the main thread and the QApplication
native event filter runs on the main thread — so all hotkey operations here
are inherently on the correct thread.  Do NOT call register() / unregister_all()
from a background thread.
"""
import logging
import ctypes
import ctypes.wintypes as wt
from PyQt6.QtCore import QObject, pyqtSignal, QAbstractNativeEventFilter, QByteArray
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_ALT = 0x0001
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

user32 = ctypes.windll.user32

VK_MAP = {
    "A": 0x41, "B": 0x42, "C": 0x43, "D": 0x44, "E": 0x45,
    "F": 0x46, "G": 0x47, "H": 0x48, "I": 0x49, "J": 0x4A,
    "K": 0x4B, "L": 0x4C, "M": 0x4D, "N": 0x4E, "O": 0x4F,
    "P": 0x50, "Q": 0x51, "R": 0x52, "S": 0x53, "T": 0x54,
    "U": 0x55, "V": 0x56, "W": 0x57, "X": 0x58, "Y": 0x59, "Z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "F1": 0x70, "F2": 0x71, "F3": 0x72, "F4": 0x73, "F5": 0x74,
    "F6": 0x75, "F7": 0x76, "F8": 0x77, "F9": 0x78, "F10": 0x79,
    "F11": 0x7A, "F12": 0x7B,
    "SPACE": 0x20, "ENTER": 0x0D, "TAB": 0x09, "ESCAPE": 0x1B,
    "BACKSPACE": 0x08, "DELETE": 0x2E, "INSERT": 0x2D,
    "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PAGEDOWN": 0x22,
    "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27,
}

MOD_MAP = {
    "CTRL": MOD_CONTROL, "CONTROL": MOD_CONTROL,
    "SHIFT": MOD_SHIFT, "ALT": MOD_ALT, "WIN": MOD_WIN,
}


def parse_shortcut(shortcut: str):
    """Parse 'Ctrl+Shift+V' into (modifiers, vk_code)."""
    parts = [p.strip().upper() for p in shortcut.replace("+", " ").split()]
    mods = 0
    vk = None
    for p in parts:
        if p in MOD_MAP:
            mods |= MOD_MAP[p]
        elif p in VK_MAP:
            vk = VK_MAP[p]
    return mods, vk


def shortcut_display(shortcut: str) -> str:
    """Normalize for display: 'ctrl+shift+v' -> 'Ctrl+Shift+V'."""
    parts = [p.strip() for p in shortcut.replace("+", " ").split()]
    result = []
    for p in parts:
        up = p.upper()
        if up in ("CTRL", "CONTROL"):
            result.append("Ctrl")
        elif up == "SHIFT":
            result.append("Shift")
        elif up == "ALT":
            result.append("Alt")
        elif up == "WIN":
            result.append("Win")
        else:
            result.append(up)
    return "+".join(result)


class NativeHotkeyFilter(QAbstractNativeEventFilter):
    """Receives WM_HOTKEY messages from the Windows message queue."""

    def __init__(self, callback):
        super().__init__()
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG" or event_type == QByteArray(b"windows_generic_MSG"):
            try:
                msg_ptr = int(message)
                msg = ctypes.cast(msg_ptr, ctypes.POINTER(wt.MSG)).contents
                if msg.message == WM_HOTKEY:
                    self._callback(int(msg.wParam))
                    return True, 0
            except Exception:
                pass
        return False, 0


class GlobalHotkeyManager(QObject):
    """Manages global hotkeys. Emits action name when a hotkey is pressed.

    1.4: registration_failed signal is emitted with (action, shortcut) when
    RegisterHotKey fails so the main window can notify the user via a tray
    notification instead of silently swallowing the error.
    """
    triggered = pyqtSignal(str)                     # action name
    registration_failed = pyqtSignal(str, str)      # (action, shortcut) — 1.4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registered: dict[int, str] = {}    # id -> action_name
        self._action_ids: dict[str, int] = {}    # action_name -> id
        self._next_id = 0xB000
        self._filter = NativeHotkeyFilter(self._on_hotkey)
        app = QApplication.instance()
        if app:
            app.installNativeEventFilter(self._filter)

    def register(self, action: str, shortcut: str) -> bool:
        """
        Register a global hotkey.

        Returns True on success.
        1.4: On failure, logs an error AND emits registration_failed(action, shortcut)
        so the caller can surface a non-blocking notification to the user.
        """
        mods, vk = parse_shortcut(shortcut)
        if vk is None:
            logger.warning("register: could not parse shortcut '%s' for action '%s'", shortcut, action)
            return False

        # Unregister existing binding for this action first
        if action in self._action_ids:
            self._unregister_one(action)

        hid = self._next_id
        self._next_id += 1

        try:
            ok = bool(user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk))
        except Exception as exc:
            logger.error("RegisterHotKey raised for action '%s' (%s): %s", action, shortcut, exc)
            ok = False

        if ok:
            self._registered[hid] = action
            self._action_ids[action] = hid
            logger.debug("Registered hotkey '%s' -> '%s' (id=%d)", action, shortcut, hid)
            return True

        # 1.4 — Registration failed (conflict with another app or OS restriction)
        err = ctypes.get_last_error()
        logger.warning(
            "RegisterHotKey FAILED for action '%s' shortcut '%s' "
            "(Win32 error %d — likely conflict with another application)",
            action, shortcut, err
        )
        self.registration_failed.emit(action, shortcut)
        return False

    def _unregister_one(self, action: str):
        hid = self._action_ids.pop(action, None)
        if hid is not None:
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception as exc:
                logger.warning("UnregisterHotKey failed for action '%s': %s", action, exc)
            self._registered.pop(hid, None)

    def unregister_all(self):
        for hid in list(self._registered.keys()):
            try:
                user32.UnregisterHotKey(None, hid)
            except Exception:
                pass
        self._registered.clear()
        self._action_ids.clear()

    def _on_hotkey(self, hotkey_id: int):
        action = self._registered.get(hotkey_id)
        if action:
            self.triggered.emit(action)

    def is_registered(self, action: str) -> bool:
        return action in self._action_ids
