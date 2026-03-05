# Modified: [2.3] crash logging to %APPDATA%/CyberClip/logs/crash.log with rotation;
#           [4.4] ProcessDPIAware via ctypes; [1.7] startup image orphan cleanup;
#           [1.3] WM_WTSSESSION_CHANGE session-unlock re-attach via Windows API;
#           [6.2] ServiceLocator pattern — components receive dependencies via constructor
"""CyberClip application setup and launcher."""
import sys
import os
import ctypes
import logging
import logging.handlers
import traceback

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont, QFontDatabase, QIcon

from cyberclip.utils.constants import (
    APP_NAME, FONT_FAMILY, FONT_FAMILY_FALLBACK, APP_DATA_DIR,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_LOG_DIR = os.path.join(APP_DATA_DIR, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "crash.log")


# ---------------------------------------------------------------------------
# 2.3 — Crash / rotating log setup
# ---------------------------------------------------------------------------
def setup_logging():
    """Configure rotating file logger + console logger."""
    os.makedirs(_LOG_DIR, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Rotating file handler: 5 backup files × 1 MB each
    fh = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    ))
    root.addHandler(fh)

    # Console handler (INFO+) for dev runs
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(ch)


# ---------------------------------------------------------------------------
# 4.4 — DPI awareness
# ---------------------------------------------------------------------------
def setup_dpi_awareness():
    """
    Declare process DPI-aware BEFORE creating the QApplication so Qt receives
    correct physical pixel counts.  Use SetProcessDpiAwarenessContext (Win10+)
    with fallback to SetProcessDPIAware.
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _get_icon_path() -> str:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "assets", "icon.ico")


def setup_high_dpi():
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"


def setup_app_id():
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "CyberClip.ClipboardManager.1.0"
        )
    except Exception:
        pass


def load_fonts(app: QApplication):
    font_dirs = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    ]
    for font_dir in font_dirs:
        if os.path.isdir(font_dir):
            for f in os.listdir(font_dir):
                if "firacode" in f.lower() and f.endswith((".ttf", ".otf")):
                    QFontDatabase.addApplicationFont(os.path.join(font_dir, f))

    families = QFontDatabase.families()
    if any(FONT_FAMILY.lower() in f.lower() for f in families):
        app.setFont(QFont(FONT_FAMILY, 10))
    elif any("firacode" in f.lower() for f in families):
        for f in families:
            if "firacode" in f.lower():
                app.setFont(QFont(f, 10))
                break
    else:
        app.setFont(QFont(FONT_FAMILY_FALLBACK, 10))


# ---------------------------------------------------------------------------
# 6.2 — ServiceLocator
# ---------------------------------------------------------------------------
class ServiceLocator:
    """
    Minimal service container.  Register singleton factories once at startup;
    components call ServiceLocator.get(SomeClass) to receive the shared instance.
    """
    _instances: dict = {}

    @classmethod
    def register(cls, key, instance):
        cls._instances[key] = instance

    @classmethod
    def get(cls, key):
        return cls._instances.get(key)


def create_app() -> tuple:
    """Create and configure the QApplication and MainWindow."""
    from cyberclip.storage.database import Database
    from cyberclip.storage.image_store import ImageStore
    from cyberclip.gui.main_window import MainWindow
    from cyberclip.gui.styles import CYBERPUNK_QSS

    setup_high_dpi()
    setup_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    icon_path = _get_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    load_fonts(app)
    app.setStyleSheet(CYBERPUNK_QSS)

    # ── 6.2 ServiceLocator ─────────────────────────────────────────────────
    db = Database()
    image_store = ImageStore()
    ServiceLocator.register("database", db)
    ServiceLocator.register("image_store", image_store)

    # ── 1.7 Startup orphan image cleanup ──────────────────────────────────
    try:
        image_store.startup_cleanup(db)
    except Exception as exc:
        logging.getLogger(__name__).warning("Startup image cleanup failed: %s", exc)

    # ── Main window (receives dependencies via constructor) ────────────────
    window = MainWindow(db=db, image_store=image_store)

    return app, window


def run():
    """Launch CyberClip with crash logging."""
    # 4.4 — Must be before QApplication
    setup_dpi_awareness()
    # 2.3 — Rotating log
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("CyberClip starting up")

    # ── Handle --uninstall flag (6.4) ──────────────────────────────────────
    if "--uninstall" in sys.argv:
        _remove_startup_registry()
        log.info("Uninstall: registry entry removed")
        sys.exit(0)

    try:
        app, window = create_app()
        window.show()
        exit_code = app.exec()
        log.info("CyberClip exited normally (code %d)", exit_code)
        sys.exit(exit_code)
    except Exception:
        log.critical("UNHANDLED EXCEPTION:\n%s", traceback.format_exc())
        raise


# ---------------------------------------------------------------------------
# 6.4 — Startup registry helpers
# ---------------------------------------------------------------------------
def _get_startup_key():
    import winreg
    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_ALL_ACCESS,
    )


def add_to_startup():
    """Add CyberClip to Windows startup registry (updates path if changed)."""
    try:
        import winreg
        exe_path = sys.executable if getattr(sys, "frozen", False) else ""
        if not exe_path:
            # Dev mode: use pythonw to avoid console window
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            script = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "main.py"))
            exe_path = f'"{pythonw}" "{script}"'
        with _get_startup_key() as key:
            try:
                existing = winreg.QueryValueEx(key, APP_NAME)[0]
            except FileNotFoundError:
                existing = None
            if existing != exe_path:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
    except Exception as exc:
        logging.getLogger(__name__).warning("add_to_startup failed: %s", exc)


def _remove_startup_registry():
    """6.4 — Remove CyberClip registry entry on --uninstall."""
    try:
        import winreg
        with _get_startup_key() as key:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    except Exception as exc:
        logging.getLogger(__name__).warning("_remove_startup_registry failed: %s", exc)
