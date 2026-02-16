"""CyberClip application setup and launcher."""
import sys
import os
import ctypes

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QCoreApplication
from PyQt6.QtGui import QFont, QFontDatabase, QIcon

from cyberclip.gui.main_window import MainWindow
from cyberclip.gui.styles import CYBERPUNK_QSS
from cyberclip.utils.constants import APP_NAME, FONT_FAMILY, FONT_FAMILY_FALLBACK


def _get_icon_path() -> str:
    """Resolve icon path for both dev and PyInstaller builds."""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "assets", "icon.ico")


def setup_high_dpi():
    """Enable High-DPI scaling for 4K monitors."""
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"


def setup_app_id():
    """Set Windows AppUserModelID for taskbar grouping."""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"CyberClip.ClipboardManager.1.0"
        )
    except Exception:
        pass


def load_fonts(app: QApplication):
    """Load FiraCode Nerd Font if available."""
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

    # Check if FiraCode is available
    families = QFontDatabase.families()
    if any(FONT_FAMILY.lower() in f.lower() for f in families):
        app.setFont(QFont(FONT_FAMILY, 10))
    elif any("firacode" in f.lower() for f in families):
        # Try any FiraCode variant
        for f in families:
            if "firacode" in f.lower():
                app.setFont(QFont(f, 10))
                break
    else:
        app.setFont(QFont(FONT_FAMILY_FALLBACK, 10))


def create_app() -> tuple:
    """Create and configure the QApplication and MainWindow."""
    setup_high_dpi()
    setup_app_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    # Set app icon
    icon_path = _get_icon_path()
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load fonts
    load_fonts(app)

    # Apply cyberpunk stylesheet
    app.setStyleSheet(CYBERPUNK_QSS)

    # Create main window
    window = MainWindow()

    return app, window


def run():
    """Launch CyberClip."""
    app, window = create_app()
    window.show()
    sys.exit(app.exec())
