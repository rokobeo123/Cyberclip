# Modified: [1.4] hotkey registration_failed → tray notification;
#           [1.5] OCR via OcrWorker QThread (never on main thread), disable button if no Tesseract;
#           [1.6] monitor.suppress_next() before every clipboard write to prevent re-capture;
#           [1.3] WM_WTSSESSION_CHANGE → monitor.on_session_unlocked() re-sync;
#           [3.3] 300ms search debounce; [4.2] position persistence after drag-drop;
#           [6.2] constructor dependency injection (db, image_store)
"""Main CyberClip window - modern clipboard manager UI."""
import os
import subprocess
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QApplication,
    QSizePolicy, QSystemTrayIcon, QMenu, QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect, QSpinBox, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation,
    QEasingCurve, QPoint, QSize, QEvent, QRect,
    QParallelAnimationGroup, QMimeData, QAbstractNativeEventFilter, QByteArray,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QPen, QBrush, QImage,
    QLinearGradient, QFont, QAction, QCursor, QGuiApplication,
    QShortcut, QKeySequence,
)
import ctypes
import ctypes.wintypes as wt

from cyberclip.storage.database import Database
from cyberclip.storage.image_store import ImageStore
from cyberclip.storage.models import ClipboardItem, AppSettings
from cyberclip.core.clipboard_monitor import ClipboardMonitor
from cyberclip.core.magazine import Magazine
from cyberclip.core.text_cleaner import to_plain_text
from cyberclip.core.safety_net import SafetyNet
from cyberclip.core.app_detector import AppDetector
from cyberclip.gui.item_widget import ClipItemWidget
from cyberclip.gui.tab_bar import TabBar
from cyberclip.gui.hud_widget import HUDWidget
from cyberclip.gui.choice_menu import ChoiceMenu
from cyberclip.gui.settings_dialog import SettingsDialog
from cyberclip.gui.styles import CYBERPUNK_QSS
from cyberclip.utils.constants import (
    APP_NAME, NEON_CYAN, NEON_PURPLE, DARK_BG, DARK_SURFACE,
    FONT_FAMILY, FONT_FAMILY_FALLBACK, TYPE_TEXT, TYPE_IMAGE,
    TYPE_URL, TYPE_FILE, TYPE_COLOR, TYPE_EMAIL, TYPE_CODE,
    DEFAULT_BLACKLIST, DEFAULT_HOTKEYS,
    TEXT_SECONDARY, ACCENT, ANIM_FAST, ANIM_NORMAL, SEARCH_DEBOUNCE_MS,
    QUICK_PASTE_MAX_ITEMS,
)
from cyberclip.core.global_hotkeys import GlobalHotkeyManager
from cyberclip.utils.i18n import set_language, t

# WM_WTSSESSION_CHANGE constants (1.3)
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8


class SessionChangeFilter(QAbstractNativeEventFilter):
    """Intercepts WM_WTSSESSION_CHANGE to detect Windows lock/unlock (1.3)."""
    def __init__(self, callback):
        super().__init__()
        self._cb = callback

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", QByteArray(b"windows_generic_MSG")):
            try:
                msg = ctypes.cast(int(message), ctypes.POINTER(wt.MSG)).contents
                if msg.message == WM_WTSSESSION_CHANGE:
                    self._cb(int(msg.wParam))
                    return False, 0  # don't consume, just observe
            except Exception:
                pass
        return False, 0


class MainWindow(QMainWindow):
    ICON_SETTINGS = "\uf013"
    ICON_CLEAR = "\uf1f8"
    ICON_GHOST = "\uf21b"
    ICON_FIFO = "\uf160"
    ICON_LIFO = "\uf161"
    ICON_STRIP = "\uf0cc"
    ICON_ENTER = "\uf2f6"
    ICON_SEARCH = "\uf002"
    ICON_MINIMIZE = "\uf2d1"
    ICON_CLOSE = "\uf00d"
    ICON_PIN_MENU = "\uf08d"
    ICON_COLLAPSE_ALL = "\uf066"
    ICON_EXPAND_ALL = "\uf065"

    def __init__(self, db: Database = None, image_store: ImageStore = None):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("CyberClipMain")
        self.setMinimumSize(380, 500)
        self.setMouseTracking(True)

        # 6.2 — Accept injected dependencies (ServiceLocator pattern in app.py)
        self.db = db if db is not None else Database()
        self.image_store = image_store if image_store is not None else ImageStore()
        self.settings = self.db.load_settings()
        self.magazine = Magazine()
        self.safety_net = SafetyNet()
        self.app_detector = AppDetector()

        # State
        self._drag_pos = None
        self._item_widgets = []
        self._current_tab = "General"
        self._ghost_mode = self.settings.ghost_mode
        self._search_query = ""
        self._pin_filter = False
        self._target_hwnd = None
        self._paste_busy = False
        self._paste_queued = 0
        self._paste_all_active = False
        self._paste_all_total = 0
        self._paste_all_done = 0
        self._paste_item_is_image = False

        # 3.3 — search debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._perform_search)

        # 1.5 — Tesseract availability (None = not yet checked, False = not found, True = found)
        self._tesseract_available = None

        # 5.1 — Quick paste popup (lazy-init)
        self._quick_paste_popup = None

        # Clipboard monitor (pass dependencies via constructor — 6.2)
        self.monitor = ClipboardMonitor(self.image_store)
        self.monitor.item_captured.connect(self._on_item_captured)

        # Build UI
        self._setup_ui()
        self._apply_settings()
        self._load_items()

        # HUD
        self.hud = HUDWidget()

        # App detector timer
        self._app_timer = QTimer(self)
        self._app_timer.timeout.connect(self._check_app_switch)
        self._app_timer.start(1000)

        # Paste watchdog
        self._paste_watchdog = QTimer(self)
        self._paste_watchdog.setSingleShot(True)
        self._paste_watchdog.timeout.connect(self._on_paste_watchdog)

        self.magazine.queue_changed.connect(self._on_queue_changed)

        # System tray
        self._setup_tray()

        # Global hotkeys
        self._setup_global_hotkeys()

        # 1.3 — Session change filter (Windows lock/unlock)
        self._session_filter = SessionChangeFilter(self._on_session_change)
        app = QApplication.instance()
        if app:
            app.installNativeEventFilter(self._session_filter)

        # Window position
        if self.settings.window_x >= 0:
            self.move(self.settings.window_x, self.settings.window_y)
            self.resize(self.settings.window_width, self.settings.window_height)
        else:
            self.resize(1000, 700)
            self._center_on_screen()

        QTimer.singleShot(100, self._enable_blur)

        # 1.5 — Check Tesseract availability once at startup (async, 500ms after launch)
        QTimer.singleShot(500, self._check_tesseract)

    # ── 1.3 Session unlock handler ────────────────────────────────────────
    def _on_session_change(self, event_type: int):
        if event_type == WTS_SESSION_UNLOCK:
            # Re-sync clipboard monitor after Windows lock/unlock
            QTimer.singleShot(500, self.monitor.on_session_unlocked)

    # ── 1.5 Tesseract availability ────────────────────────────────────────
    def _check_tesseract(self):
        from cyberclip.core.ocr_scanner import is_tesseract_available
        self._tesseract_available = is_tesseract_available()
        if not self._tesseract_available:
            # Disable OCR buttons on all existing widgets
            for w in self._item_widgets:
                self._update_ocr_button_state(w)

    def _update_ocr_button_state(self, widget: ClipItemWidget):
        """Disable OCR action buttons if Tesseract is not available."""
        if self._tesseract_available is False:
            for btn in widget.findChildren(QPushButton):
                if btn.toolTip() == t("ocr_scan"):
                    btn.setEnabled(False)
                    btn.setToolTip(t("ocr_no_tesseract"))

    # ──────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setMouseTracking(True)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        # ── Custom Title Bar ──
        title_bar = QWidget()
        title_bar.setObjectName("TitleBar")
        title_bar.setFixedHeight(42)
        title_bar.mousePressEvent = self._title_mouse_press
        title_bar.mouseMoveEvent = self._title_mouse_move
        title_bar.mouseReleaseEvent = self._title_mouse_release
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(14, 0, 8, 0)
        tb_layout.setSpacing(8)

        title_label = QLabel(APP_NAME)
        title_label.setObjectName("TitleLabel")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        self.ghost_indicator = QLabel("\uf21b  GHOST")
        self.ghost_indicator.setObjectName("GhostIndicator")
        self.ghost_indicator.setVisible(self._ghost_mode)
        tb_layout.addWidget(self.ghost_indicator)

        self._settings_btn = QPushButton(self.ICON_SETTINGS)
        self._settings_btn.setObjectName("TitleButton")
        self._settings_btn.setFixedSize(32, 28)
        self._settings_btn.setToolTip(t("settings"))
        self._settings_btn.clicked.connect(self._open_settings)
        tb_layout.addWidget(self._settings_btn)

        self._min_btn = QPushButton(self.ICON_MINIMIZE)
        self._min_btn.setObjectName("TitleButton")
        self._min_btn.setFixedSize(32, 28)
        self._min_btn.clicked.connect(self._minimize_to_tray)
        tb_layout.addWidget(self._min_btn)

        self._close_btn = QPushButton(self.ICON_CLOSE)
        self._close_btn.setObjectName("CloseButton")
        self._close_btn.setFixedSize(32, 28)
        self._close_btn.clicked.connect(self._minimize_to_tray)
        tb_layout.addWidget(self._close_btn)

        main_layout.addWidget(title_bar)

        # ── Search Bar ──
        search_container = QWidget()
        search_container.setStyleSheet("background: transparent; padding: 4px 8px;")
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(12, 4, 12, 4)

        search_icon = QLabel(self.ICON_SEARCH)
        search_icon.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 13px; background: transparent;")
        search_icon.setFixedWidth(24)

        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("SearchBar")
        self.search_bar.setPlaceholderText(t("search_placeholder"))
        # 3.3 — debounce: start timer on every keystroke
        self.search_bar.textChanged.connect(self._on_search)
        self.search_bar.setFixedHeight(34)

        search_layout.addWidget(search_icon)
        search_layout.addWidget(self.search_bar)
        main_layout.addWidget(search_container)

        # ── Tab Bar ──
        self.tab_bar = TabBar()
        self.tab_bar.tab_changed.connect(self._on_tab_changed)
        main_layout.addWidget(self.tab_bar)

        # ── Toolbar ──
        toolbar = QWidget()
        toolbar.setObjectName("Toolbar")
        toolbar.setFixedHeight(38)
        tb2_layout = QHBoxLayout(toolbar)
        tb2_layout.setContentsMargins(8, 0, 8, 0)
        tb2_layout.setSpacing(4)

        self.mode_btn = QPushButton(self.ICON_FIFO + "  FIFO")
        self.mode_btn.setObjectName("ToolButton")
        self.mode_btn.setCheckable(True)
        self.mode_btn.setToolTip(t("picking_style"))
        self.mode_btn.clicked.connect(self._toggle_mode)
        tb2_layout.addWidget(self.mode_btn)

        self.strip_btn = QPushButton(self.ICON_STRIP + "  Clean")
        self.strip_btn.setObjectName("ToolButton")
        self.strip_btn.setCheckable(True)
        self.strip_btn.setChecked(self.settings.strip_formatting)
        self.strip_btn.setToolTip(t("strip_formatting"))
        self.strip_btn.clicked.connect(self._toggle_strip)
        tb2_layout.addWidget(self.strip_btn)

        self.enter_btn = QPushButton(self.ICON_ENTER + "  Auto↵")
        self.enter_btn.setObjectName("ToolButton")
        self.enter_btn.setCheckable(True)
        self.enter_btn.setChecked(self.settings.auto_enter)
        self.enter_btn.setToolTip(t("auto_enter"))
        self.enter_btn.clicked.connect(self._toggle_auto_enter)
        tb2_layout.addWidget(self.enter_btn)

        self.tab_btn = QPushButton("\uf0e5" + "  Auto⇥")
        self.tab_btn.setObjectName("ToolButton")
        self.tab_btn.setCheckable(True)
        self.tab_btn.setChecked(self.settings.auto_tab)
        self.tab_btn.setToolTip(t("auto_tab"))
        self.tab_btn.clicked.connect(self._toggle_auto_tab)
        tb2_layout.addWidget(self.tab_btn)

        tb2_layout.addStretch()

        _pac_label = QLabel("×")
        _pac_label.setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        _pac_label.setToolTip(t("paste_all_count_tooltip"))
        tb2_layout.addWidget(_pac_label)

        self.paste_count_spin = QSpinBox()
        self.paste_count_spin.setRange(0, 99)
        self.paste_count_spin.setSpecialValueText("∞")
        self.paste_count_spin.setValue(getattr(self.settings, 'paste_all_count', 0))
        self.paste_count_spin.setFixedWidth(52)
        self.paste_count_spin.setFixedHeight(26)
        self.paste_count_spin.setToolTip(t("paste_all_count_tooltip"))
        self.paste_count_spin.setStyleSheet(
            "QSpinBox { background: #2C2C2E; border: 1px solid rgba(255,255,255,0.1); "
            "border-radius: 5px; padding: 0 4px; color: #E0E0E0; font-size: 12px; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 14px; }"
        )
        self.paste_count_spin.valueChanged.connect(self._on_paste_count_changed)
        tb2_layout.addWidget(self.paste_count_spin)

        self._reset_btn = QPushButton("\uf0e2")
        self._reset_btn.setObjectName("ToolButton")
        self._reset_btn.setToolTip(t("reset_queue"))
        self._reset_btn.clicked.connect(self._reset_magazine)
        tb2_layout.addWidget(self._reset_btn)

        self.pin_filter_btn = QPushButton(self.ICON_PIN_MENU)
        self.pin_filter_btn.setObjectName("ToolButton")
        self.pin_filter_btn.setCheckable(True)
        self.pin_filter_btn.setToolTip(t("pin_filter"))
        self.pin_filter_btn.clicked.connect(self._toggle_pin_filter)
        tb2_layout.addWidget(self.pin_filter_btn)

        self._all_collapsed = False
        self.collapse_all_btn = QPushButton(self.ICON_EXPAND_ALL)
        self.collapse_all_btn.setObjectName("ToolButton")
        self.collapse_all_btn.setToolTip(t("expand_all"))
        self.collapse_all_btn.clicked.connect(self._toggle_collapse_all)
        tb2_layout.addWidget(self.collapse_all_btn)

        self.ghost_btn = QPushButton(self.ICON_GHOST)
        self.ghost_btn.setObjectName("ToolButton")
        self.ghost_btn.setCheckable(True)
        self.ghost_btn.setChecked(self._ghost_mode)
        self.ghost_btn.setToolTip(t("ghost_mode"))
        self.ghost_btn.clicked.connect(self._toggle_ghost_mode)
        tb2_layout.addWidget(self.ghost_btn)

        self._clear_btn = QPushButton(self.ICON_CLEAR)
        self._clear_btn.setObjectName("ToolButton")
        self._clear_btn.setProperty("danger", True)
        self._clear_btn.setToolTip(t("clear_tab"))
        self._clear_btn.clicked.connect(self._clear_tab)
        tb2_layout.addWidget(self._clear_btn)

        main_layout.addWidget(toolbar)

        # ── Clip List ──
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_container.setAcceptDrops(True)
        self.list_container.dragEnterEvent = self._list_drag_enter
        self.list_container.dragMoveEvent = self._list_drag_move
        self.list_container.dropEvent = self._list_drop
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(6, 4, 6, 4)
        self.list_layout.setSpacing(4)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.list_container)
        main_layout.addWidget(self.scroll_area, 1)

        # ── Empty State ──
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_icon = QLabel("◈")
        empty_icon.setObjectName("EmptyIcon")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        self._empty_text = QLabel(t("empty_title") + "\n" + t("empty_subtitle"))
        self._empty_text.setObjectName("EmptyState")
        self._empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(self._empty_text)
        self.list_layout.addWidget(self.empty_widget)

        # ── Status Bar ──
        status_bar = QWidget()
        status_bar.setObjectName("StatusBar")
        status_bar.setFixedHeight(30)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel(t("ready"))
        self.status_label.setObjectName("StatusLabel")
        sb_layout.addWidget(self.status_label)
        sb_layout.addStretch()

        self.magazine_label = QLabel("")
        self.magazine_label.setObjectName("MagazineCounter")
        sb_layout.addWidget(self.magazine_label)

        self.count_label = QLabel(t("items_count", count=0))
        self.count_label.setObjectName("StatusLabel")
        sb_layout.addWidget(self.count_label)

        main_layout.addWidget(status_bar)

    # ── Paint ────────────────────────────────────────────────────────────
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setBrush(QColor(28, 28, 30, 248))
        pen = QPen(QColor(255, 255, 255, 18))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 14, 14)
        painter.end()

    # ── Edge resize ───────────────────────────────────────────────────────
    _RESIZE_BORDER = 8

    def _edge_zone(self, pos):
        r = self.rect()
        b = self._RESIZE_BORDER
        left = pos.x() < b
        right = pos.x() > r.width() - b
        top = pos.y() < b
        bottom = pos.y() > r.height() - b
        if top and left:     return "tl"
        if top and right:    return "tr"
        if bottom and left:  return "bl"
        if bottom and right: return "br"
        if left:   return "l"
        if right:  return "r"
        if top:    return "t"
        if bottom: return "b"
        return None

    _CURSOR_MAP = {
        "l": Qt.CursorShape.SizeHorCursor, "r": Qt.CursorShape.SizeHorCursor,
        "t": Qt.CursorShape.SizeVerCursor, "b": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor, "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor, "bl": Qt.CursorShape.SizeBDiagCursor,
    }

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._edge_zone(event.pos())
            if zone:
                self._resize_edge = zone
                self._resize_start_pos = event.globalPosition().toPoint()
                self._resize_start_geo = self.geometry()
                event.accept()
                return
        self._resize_edge = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_resize_edge') and self._resize_edge and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._resize_start_pos
            geo = QRect(self._resize_start_geo)
            edge = self._resize_edge
            min_w, min_h = self.minimumWidth(), self.minimumHeight()
            if "r" in edge: geo.setRight(geo.right() + delta.x())
            if "b" in edge: geo.setBottom(geo.bottom() + delta.y())
            if "l" in edge: geo.setLeft(min(geo.left() + delta.x(), geo.right() - min_w))
            if "t" in edge: geo.setTop(min(geo.top() + delta.y(), geo.bottom() - min_h))
            if geo.width() >= min_w and geo.height() >= min_h:
                self.setGeometry(geo)
            event.accept()
            return
        zone = self._edge_zone(event.pos())
        if zone and zone in self._CURSOR_MAP:
            self.setCursor(self._CURSOR_MAP[zone])
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._resize_edge = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    # ── Title bar drag ────────────────────────────────────────────────────
    def _title_mouse_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def _title_mouse_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def _title_mouse_release(self, event):
        self._drag_pos = None

    # ═══════════════════════════════════════════════════
    #  ITEM MANAGEMENT
    # ═══════════════════════════════════════════════════
    @pyqtSlot(ClipboardItem)
    def _on_item_captured(self, item: ClipboardItem):
        tab = self.app_detector.detect_tab()
        item.tab = tab or self._current_tab

        # Skip exact duplicate of latest visible item
        if item.content_type != TYPE_IMAGE and self._item_widgets:
            latest = self._item_widgets[0].item
            if latest.text_content == item.text_content and latest.content_type == item.content_type:
                return

        self.db.add_item(item, max_items=getattr(self.settings, 'max_items', 200))
        self.magazine.add(item)

        if item.tab == self._current_tab or not self._current_tab:
            self._add_item_widget(item, animate=True)
            self._update_empty_state()
            self._update_count()

        tabs = self.db.get_tabs()
        self.tab_bar.set_tabs(tabs)

        self.hud.notify(f"📋 {item.preview[:30]}", 2000)
        self.status_label.setText(t("copied_ctrlv"))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _load_items(self):
        for w in self._item_widgets:
            w.deleteLater()
        self._item_widgets.clear()

        if self._search_query:
            items = self.db.search_items(self._search_query, self._current_tab)
        else:
            items = self.db.get_items(self._current_tab)

        if self._pin_filter:
            items = [i for i in items if i.pinned]

        fifo_items = self.db.get_items_fifo(self._current_tab)
        self.magazine.load(fifo_items)

        for item in items:
            self._add_item_widget(item, animate=False)

        self._update_empty_state()
        self._update_count()
        self._highlight_magazine_item()

        tabs = self.db.get_tabs()
        self.tab_bar.set_tabs(tabs)

        # 1.5 — update OCR button states after load
        if self._tesseract_available is False:
            for w in self._item_widgets:
                self._update_ocr_button_state(w)

    def _add_item_widget(self, item: ClipboardItem, animate: bool = False):
        widget = ClipItemWidget(item)
        widget.clicked.connect(self._on_item_clicked)
        widget.paste_requested.connect(self._paste_item)
        widget.delete_requested.connect(self._delete_item)
        widget.pin_toggled.connect(self._toggle_pin)
        widget.ocr_requested.connect(self._ocr_item)
        widget.open_file_requested.connect(self._open_file)
        widget.start_from_here.connect(self._start_from_here)
        widget.view_image_requested.connect(self._view_image)
        widget.transform_requested.connect(self._on_transform_requested)    # 5.2
        widget.save_snippet_requested.connect(self._on_save_snippet)         # 5.4

        self.list_layout.insertWidget(0, widget)
        self._item_widgets.insert(0, widget)

        # 1.5 — immediately disable OCR button if no Tesseract
        if self._tesseract_available is False:
            self._update_ocr_button_state(widget)

        if animate:
            widget.animate_in(delay_ms=0)

    def _update_empty_state(self):
        self.empty_widget.setVisible(len(self._item_widgets) == 0)

    def _update_count(self):
        self.count_label.setText(t("items_count", count=len(self._item_widgets)))

    # ═══════════════════════════════════════════════════
    #  ITEM ACTIONS
    # ═══════════════════════════════════════════════════
    @pyqtSlot(ClipboardItem)
    def _paste_item(self, item: ClipboardItem):
        """Copy item to clipboard so user can paste it anywhere."""
        # 1.6 — suppress monitor BEFORE writing to clipboard
        self.monitor.suppress_next()
        self.monitor.pause()

        clipboard = QApplication.clipboard()

        if item.content_type == TYPE_IMAGE and item.image_path and os.path.exists(item.image_path):
            img = QImage(item.image_path)
            if not img.isNull():
                mime = QMimeData()
                mime.setImageData(img)
                clipboard.setMimeData(mime)
        else:
            text = item.text_content
            if self.settings.strip_formatting:
                text = to_plain_text(text)
            clipboard.setText(text)

        QTimer.singleShot(500, self.monitor.resume)

        self.status_label.setText(t("copied_ctrlv"))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _sequential_paste(self):
        try:
            if self._paste_busy:
                self._paste_queued += 1
                return

            item = self.magazine.fire()
            if not item:
                self._paste_queued = 0
                self._paste_all_active = False
                msg = t("queue_empty")
                self.hud.notify(msg, 2000)
                self.status_label.setText(msg)
                QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
                return

            self._paste_busy = True
            self._paste_watchdog.start(6000)

            # 1.6 — suppress BEFORE writing to clipboard
            self.monitor.suppress_next()
            self.monitor.pause()

            try:
                clipboard = QApplication.clipboard()
                if item.content_type == TYPE_IMAGE and item.image_path and os.path.exists(item.image_path):
                    img = QImage(item.image_path)
                    if not img.isNull():
                        mime = QMimeData()
                        mime.setImageData(img)
                        clipboard.setMimeData(mime)
                        QApplication.processEvents()
                        self._paste_item_is_image = True
                    else:
                        self._paste_busy = False
                        self._paste_item_is_image = False
                        QTimer.singleShot(0, self._after_paste)
                        return
                else:
                    text = item.text_content
                    if self.settings.strip_formatting:
                        text = to_plain_text(text)
                    clipboard.setText(text)
                    self._paste_item_is_image = False

                self._highlight_magazine_item()

            except Exception:
                self._paste_busy = False
                self._paste_item_is_image = False
                QTimer.singleShot(0, self._after_paste)
                return

            settle_ms = 300 if self._paste_item_is_image else 100
            QTimer.singleShot(settle_ms, self._do_inject_paste)

        except Exception:
            self._paste_busy = False
            self._paste_all_active = False
            self._paste_queued = 0
            self._paste_watchdog.stop()
            self.monitor.resume()

    def _do_inject_paste(self):
        try:
            from cyberclip.utils.win32_helpers import (
                send_ctrl_v_fast, send_key, set_foreground,
                VK_RETURN, VK_TAB, KEYEVENTF_KEYUP,
            )
            import time

            if self._target_hwnd:
                set_foreground(self._target_hwnd)
                time.sleep(0.15)

            send_ctrl_v_fast()

            if self.settings.auto_enter:
                time.sleep(0.02)
                send_key(vk=VK_RETURN)
                time.sleep(0.01)
                send_key(vk=VK_RETURN, flags=KEYEVENTF_KEYUP)
            elif self.settings.auto_tab:
                time.sleep(0.02)
                send_key(vk=VK_TAB)
                time.sleep(0.01)
                send_key(vk=VK_TAB, flags=KEYEVENTF_KEYUP)

            QTimer.singleShot(60, self._after_paste)
        except Exception:
            self._paste_busy = False
            QTimer.singleShot(0, self._after_paste)

    def _after_paste(self):
        try:
            self._paste_busy = False
            self._paste_watchdog.stop()
            QTimer.singleShot(200, self.monitor.resume)

            if self._paste_all_active:
                self._paste_all_done += 1

            peek = self.magazine.peek()

            if self._paste_all_active and self._paste_all_total > 0:
                remaining = self._paste_all_total - self._paste_all_done
                if peek and remaining > 0:
                    msg = t("paste_all_progress",
                            done=self._paste_all_done,
                            total=self._paste_all_total,
                            preview=peek.preview[:30])
                else:
                    msg = t("paste_all_done", total=self._paste_all_done)
            elif peek:
                msg = t("pasted_next", preview=peek.preview[:30])
            else:
                msg = t("pasted_done")

            self.hud.notify(msg, 2000)
            self.status_label.setText(msg)
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

            if self._paste_queued > 0:
                self._paste_queued -= 1
                self._target_hwnd = None
                QTimer.singleShot(20, self._sequential_paste)
            elif self._paste_all_active and peek and self._paste_all_done < self._paste_all_total:
                base_delay = max(getattr(self.settings, 'paste_delay_ms', 500), 300)
                inter_delay = base_delay * 2 if self._paste_item_is_image else base_delay
                QTimer.singleShot(inter_delay, self._sequential_paste)
            else:
                self._target_hwnd = None
                self._paste_item_is_image = False
                if self._paste_all_active:
                    self._paste_all_active = False
                    self._paste_all_total = 0
                    self._paste_all_done = 0
        except Exception:
            self._paste_busy = False
            self._paste_all_active = False
            self._paste_queued = 0
            self._target_hwnd = None
            self._paste_all_total = 0
            self._paste_all_done = 0
            self._paste_item_is_image = False
            self._paste_watchdog.stop()

    def _on_paste_watchdog(self):
        self._paste_busy = False
        self._paste_all_active = False
        self._paste_queued = 0
        self._target_hwnd = None
        self._paste_all_total = 0
        self._paste_all_done = 0
        self._paste_item_is_image = False
        self.monitor.resume()
        msg = t("paste_timeout")
        self.hud.notify(msg, 3000)
        self.status_label.setText(msg)
        QTimer.singleShot(3000, lambda: self.status_label.setText(t("ready")))

    def _highlight_magazine_item(self):
        current = self.magazine.peek()
        for w in self._item_widgets:
            is_current = (current is not None) and (w.item.id == current.id)
            w.set_magazine_active(is_current)

    @pyqtSlot(ClipboardItem)
    def _delete_item(self, item: ClipboardItem):
        for w in self._item_widgets:
            if w.item.id == item.id:
                self._item_widgets.remove(w)
                w.animate_out(callback=lambda: self._finalize_delete(w, item))
                break

    def _finalize_delete(self, widget, item):
        # 1.7 — db.delete_item now handles image file deletion atomically
        self.db.delete_item(item.id)
        widget.deleteLater()
        self._update_empty_state()
        self._update_count()

    @pyqtSlot(ClipboardItem)
    def _toggle_pin(self, item: ClipboardItem):
        new_state = self.db.toggle_pin(item.id)
        for w in self._item_widgets:
            if w.item.id == item.id:
                w.update_pin_state(new_state)
                break

    # ── 1.5 OCR via QThread worker ────────────────────────────────────────
    @pyqtSlot(ClipboardItem)
    def _ocr_item(self, item: ClipboardItem):
        from cyberclip.core.ocr_scanner import is_tesseract_available, OcrWorker, TESSERACT_INSTALL_INSTRUCTIONS

        if not is_tesseract_available():
            self.status_label.setText(t("ocr_no_tesseract"))
            self.tray_icon.showMessage(
                APP_NAME,
                TESSERACT_INSTALL_INSTRUCTIONS[:200],
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
            QTimer.singleShot(4000, lambda: self.status_label.setText(t("ready")))
            return

        self.status_label.setText(t("ocr_scanning"))

        worker = OcrWorker(item.image_path, self)
        worker.ocr_done.connect(self._on_ocr_done)
        worker.ocr_error.connect(self._on_ocr_error)
        # Keep reference so GC doesn't collect it
        self._ocr_worker = worker
        worker.start()

    @pyqtSlot(str)
    def _on_ocr_done(self, text: str):
        # 1.6 — suppress monitor before writing OCR result to clipboard
        self.monitor.suppress_next()
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.status_label.setText(t("ocr_extracted", count=len(text)))
        QTimer.singleShot(3000, lambda: self.status_label.setText(t("ready")))

    @pyqtSlot(str)
    def _on_ocr_error(self, msg: str):
        self.status_label.setText(t("ocr_no_text"))
        QTimer.singleShot(3000, lambda: self.status_label.setText(t("ready")))

    @pyqtSlot(str)
    def _open_file(self, path: str):
        if os.path.exists(path):
            if os.path.isdir(path):
                subprocess.Popen(f'explorer "{path}"')
            else:
                subprocess.Popen(f'explorer /select,"{path}"')

    @pyqtSlot(ClipboardItem)
    def _view_image(self, item: ClipboardItem):
        from cyberclip.gui.image_viewer import ImageViewerDialog
        if item.image_path and os.path.exists(item.image_path):
            viewer = ImageViewerDialog(item.image_path, self)
            viewer.exec()

    @pyqtSlot(ClipboardItem)
    def _on_item_clicked(self, item: ClipboardItem):
        for w in self._item_widgets:
            w.set_selected(w.item.id == item.id)
        if self.magazine.set_start(item.id):
            self._highlight_magazine_item()
            peek = self.magazine.peek()
            if peek:
                self.status_label.setText(f"▶ {t('start_from_here')}: {peek.preview[:40]}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    @pyqtSlot(ClipboardItem)
    def _start_from_here(self, item: ClipboardItem):
        self._on_item_clicked(item)

    # ── Drag & Drop reordering ─────────────────────────────────────────────
    def _list_drag_enter(self, event):
        if event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            event.acceptProposedAction()

    def _list_drag_move(self, event):
        if event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            event.acceptProposedAction()
            target_idx = self._drop_index_at(event.position().toPoint())
            for i, w in enumerate(self._item_widgets):
                w.setProperty("drop_target", "true" if i == target_idx else "false")
                w.style().unpolish(w)
                w.style().polish(w)

    def _list_drop(self, event):
        if not event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            return
        for w in self._item_widgets:
            w.setProperty("drop_target", "false")
            w.style().unpolish(w)
            w.style().polish(w)

        dragged_id = int(event.mimeData().data(
            "application/x-cyberclip-item-id").data().decode())
        target_idx = self._drop_index_at(event.position().toPoint())

        dragged_widget = None
        dragged_idx = -1
        for i, w in enumerate(self._item_widgets):
            if w.item.id == dragged_id:
                dragged_widget = w
                dragged_idx = i
                break
        if dragged_widget is None or dragged_idx == target_idx:
            return

        self._item_widgets.pop(dragged_idx)
        if target_idx > dragged_idx:
            target_idx -= 1
        target_idx = max(0, min(target_idx, len(self._item_widgets)))
        self._item_widgets.insert(target_idx, dragged_widget)

        while self.list_layout.count():
            self.list_layout.takeAt(0)
        for w in self._item_widgets:
            self.list_layout.addWidget(w)
        self.list_layout.addWidget(self.empty_widget)

        new_ids = [w.item.id for w in self._item_widgets]
        self.magazine.reorder(new_ids)
        # 4.2 — persist new order to SQLite
        self.db.update_positions(new_ids)
        self._highlight_magazine_item()

        event.acceptProposedAction()

    def _drop_index_at(self, pos):
        for i, w in enumerate(self._item_widgets):
            widget_rect = w.geometry()
            mid_y = widget_rect.top() + widget_rect.height() // 2
            if pos.y() < mid_y:
                return i
        return len(self._item_widgets)

    # ═══════════════════════════════════════════════════
    #  MAGAZINE / QUEUE
    # ═══════════════════════════════════════════════════
    def _fire_magazine(self):
        self._sequential_paste()

    def _paste_all(self):
        if self._paste_all_active:
            self._paste_all_active = False
            self.status_label.setText(t("paste_all_stop"))
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
            return
        if self._paste_busy:
            self.status_label.setText(t("paste_busy"))
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
            return
        if not self.magazine.peek():
            self.status_label.setText(t("queue_empty"))
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
            return

        limit = getattr(self.settings, 'paste_all_count', 0)
        total = self.magazine.remaining
        count = min(total, limit) if limit > 0 else total

        # 4.1 — Confirm dialog when pasting more than 10 items
        if count > 10:
            reply = QMessageBox.question(
                self,
                t("paste_all_confirm_title"),
                t("paste_all_confirm_msg", count=count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        try:
            from cyberclip.utils.win32_helpers import get_foreground_hwnd
            self._target_hwnd = get_foreground_hwnd()
        except Exception:
            self._target_hwnd = None

        self._paste_all_active = True
        self._paste_all_done = 0
        self._paste_all_total = count
        self.hud.notify(t("paste_all_start", count=self._paste_all_total), 3000)
        self._sequential_paste()

    def _on_paste_count_changed(self, value: int):
        self.settings.paste_all_count = value
        self.db.save_setting("paste_all_count", value)

    def _skip_magazine(self):
        item = self.magazine.fire()
        if item:
            self._highlight_magazine_item()
            peek = self.magazine.peek()
            if peek:
                self.status_label.setText(t("skip_next", preview=peek.preview[:40]))
            else:
                self.status_label.setText(t("skip_done"))
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
        else:
            self.status_label.setText(t("queue_empty"))
            QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    @pyqtSlot(int, int)
    def _on_queue_changed(self, index, total):
        if total > 0 and index < total:
            pos_label = f"[{index+1}/{total}]"
            self.magazine_label.setText(f"▶ {pos_label}")
        elif total > 0 and index >= total:
            self.magazine_label.setText(f"✓ {total}/{total}")
            pos_label = f"[{total}/{total}]"
        else:
            self.magazine_label.setText("")
            pos_label = ""
        # 4.1 — Update tray tooltip with current position
        if pos_label:
            self.tray_icon.setToolTip(f"{APP_NAME} {pos_label}")
        else:
            self.tray_icon.setToolTip(APP_NAME)
        peek = self.magazine.peek()
        self.hud.update_info(index, total, peek.preview if peek else "")
        self._highlight_magazine_item()

    # ═══════════════════════════════════════════════════
    #  GLOBAL HOTKEYS
    # ═══════════════════════════════════════════════════
    def _setup_global_hotkeys(self):
        self._hotkey_mgr = GlobalHotkeyManager(self)
        self._hotkey_mgr.triggered.connect(self._on_global_hotkey)
        # 1.4 — connect registration failure to non-blocking tray notification
        self._hotkey_mgr.registration_failed.connect(self._on_hotkey_registration_failed)

        hotkeys = dict(DEFAULT_HOTKEYS)
        if self.settings.hotkeys:
            for k, v in self.settings.hotkeys.items():
                if k in hotkeys:
                    hotkeys[k] = v
        self.settings.hotkeys = hotkeys

        for action, shortcut in hotkeys.items():
            self._hotkey_mgr.register(action, shortcut)

    # 1.4 — non-blocking notification when hotkey registration fails
    @pyqtSlot(str, str)
    def _on_hotkey_registration_failed(self, action: str, shortcut: str):
        msg = t("hotkey_conflict", action=action, shortcut=shortcut)
        try:
            self.tray_icon.showMessage(
                APP_NAME,
                msg,
                QSystemTrayIcon.MessageIcon.Warning,
                5000,
            )
        except Exception:
            pass
        self.status_label.setText(msg)
        QTimer.singleShot(4000, lambda: self.status_label.setText(t("ready")))

    def _on_global_hotkey(self, action: str):
        if action == "sequential_paste":
            self._sequential_paste()
        elif action == "paste_all":
            self._paste_all()
        elif action == "toggle_window":
            if self.isVisible():
                self._animate_hide()
            else:
                self._animate_show()
        elif action == "skip_item":
            self._skip_magazine()
        elif action == "ghost_mode":
            self._toggle_ghost_mode()
        elif action == "quick_paste":        # 5.1
            self._show_quick_paste_popup()

    def _reload_hotkeys(self):
        self._hotkey_mgr.unregister_all()
        hotkeys = dict(DEFAULT_HOTKEYS)
        if self.settings.hotkeys:
            for k, v in self.settings.hotkeys.items():
                if k in hotkeys:
                    hotkeys[k] = v
        self.settings.hotkeys = hotkeys
        for action, shortcut in hotkeys.items():
            self._hotkey_mgr.register(action, shortcut)

    # ═══════════════════════════════════════════════════
    #  TOOLBAR ACTIONS
    # ═══════════════════════════════════════════════════
    def _toggle_mode(self):
        if self.settings.picking_style == "FIFO":
            self.settings.picking_style = "LIFO"
            self.mode_btn.setText(self.ICON_LIFO + "  LIFO")
        else:
            self.settings.picking_style = "FIFO"
            self.mode_btn.setText(self.ICON_FIFO + "  FIFO")
        self.magazine.set_mode(self.settings.picking_style)
        self._highlight_magazine_item()
        self.db.save_all_settings(self.settings)

    def _toggle_strip(self):
        self.settings.strip_formatting = self.strip_btn.isChecked()
        self.db.save_all_settings(self.settings)

    def _toggle_auto_enter(self):
        self.settings.auto_enter = self.enter_btn.isChecked()
        if self.settings.auto_enter:
            self.settings.auto_tab = False
            self.tab_btn.setChecked(False)
        self.db.save_all_settings(self.settings)

    def _toggle_auto_tab(self):
        self.settings.auto_tab = self.tab_btn.isChecked()
        if self.settings.auto_tab:
            self.settings.auto_enter = False
            self.enter_btn.setChecked(False)
        self.db.save_all_settings(self.settings)

    def _toggle_ghost_mode(self):
        self._ghost_mode = not self._ghost_mode
        self.settings.ghost_mode = self._ghost_mode
        self.monitor.set_ghost_mode(self._ghost_mode)
        self.ghost_indicator.setVisible(self._ghost_mode)
        self.ghost_btn.setChecked(self._ghost_mode)
        if hasattr(self, '_tray_ghost_action'):
            self._tray_ghost_action.setChecked(self._ghost_mode)
        self.hud.set_ghost_mode(self._ghost_mode)
        self.db.save_all_settings(self.settings)
        # 2.2 — Change tray icon to indicate ghost mode is active
        self._update_tray_icon()
        self.status_label.setText(t("ghost_on") if self._ghost_mode else t("ghost_off"))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _clear_tab(self):
        self.db.clear_tab(self._current_tab)
        self._load_items()
        self.status_label.setText(t("cleared_tab", tab=self._current_tab))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _reset_magazine(self):
        self.magazine.reset()
        self._highlight_magazine_item()
        mode_name = "FIFO" if self.settings.picking_style == "FIFO" else "LIFO"
        self.status_label.setText(t("queue_reset", mode=mode_name))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _toggle_pin_filter(self):
        self._pin_filter = self.pin_filter_btn.isChecked()
        self._load_items()
        if self._pin_filter:
            self.status_label.setText(t("pin_only"))
        else:
            self.status_label.setText(t("show_all"))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    def _toggle_collapse_all(self):
        self._all_collapsed = not self._all_collapsed
        for w in self._item_widgets:
            if self._all_collapsed and not w._collapsed:
                w._toggle_collapse()
            elif not self._all_collapsed and w._collapsed:
                w._toggle_collapse()
        if self._all_collapsed:
            self.collapse_all_btn.setText(self.ICON_COLLAPSE_ALL)
            self.collapse_all_btn.setToolTip(t("collapse_all"))
        else:
            self.collapse_all_btn.setText(self.ICON_EXPAND_ALL)
            self.collapse_all_btn.setToolTip(t("expand_all"))

    # ═══════════════════════════════════════════════════
    #  SEARCH (3.3 — debounced)
    # ═══════════════════════════════════════════════════
    def _on_search(self, text: str):
        """Restart debounce timer on every keystroke."""
        self._search_query = text.strip()
        self._search_timer.start()  # restarts if already running

    def _perform_search(self):
        """Actually execute the search after debounce delay."""
        self._load_items()

    # ═══════════════════════════════════════════════════
    #  TAB SWITCHING
    # ═══════════════════════════════════════════════════
    def _on_tab_changed(self, tab: str):
        self._current_tab = tab
        self._load_items()

    def _check_app_switch(self):
        tab = self.app_detector.detect_tab()
        if tab and tab != self._current_tab:
            self.tab_bar.add_tab(tab)
            self.tab_bar.set_active(tab)

    # ═══════════════════════════════════════════════════
    #  SHOW / HIDE ANIMATIONS
    # ═══════════════════════════════════════════════════
    def _animate_show(self):
        try:
            from cyberclip.utils.win32_helpers import get_foreground_hwnd
            self._target_hwnd = get_foreground_hwnd()
        except Exception:
            self._target_hwnd = None

        self.show()
        self.setWindowOpacity(0.0)

        group = QParallelAnimationGroup(self)
        opacity = QPropertyAnimation(self, b"windowOpacity")
        opacity.setDuration(300)
        opacity.setStartValue(0.0)
        opacity.setEndValue(1.0)
        opacity.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(opacity)
        group.start()
        self._show_anim = group
        self.activateWindow()
        self.search_bar.setFocus()

    def _animate_hide(self):
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self.hide)
        anim.start()
        self._hide_anim = anim

    # ═══════════════════════════════════════════════════
    #  SETTINGS
    # ═══════════════════════════════════════════════════
    def _open_settings(self):
        dialog = SettingsDialog(self.settings, self)
        dialog.settings_changed.connect(self._apply_new_settings)
        dialog.exec()

    @pyqtSlot(AppSettings)
    def _apply_new_settings(self, settings: AppSettings):
        self.settings = settings
        self.db.save_all_settings(settings)
        self._apply_settings()
        self._reload_hotkeys()

    def _apply_settings(self):
        lang = getattr(self.settings, 'language', 'vi')
        set_language(lang)

        self.magazine.set_mode(self.settings.picking_style)
        self.monitor.set_blacklist(self.settings.blacklist or DEFAULT_BLACKLIST)
        self.monitor.set_ghost_mode(self.settings.ghost_mode)

        if self.settings.picking_style == "LIFO":
            self.mode_btn.setText(self.ICON_LIFO + "  LIFO")
            self.mode_btn.setChecked(True)
        else:
            self.mode_btn.setText(self.ICON_FIFO + "  FIFO")
            self.mode_btn.setChecked(False)

        self.strip_btn.setChecked(self.settings.strip_formatting)
        self.enter_btn.setChecked(self.settings.auto_enter)
        self.tab_btn.setChecked(self.settings.auto_tab)
        self.ghost_btn.setChecked(self.settings.ghost_mode)
        self.ghost_indicator.setVisible(self.settings.ghost_mode)

        self.paste_count_spin.blockSignals(True)
        self.paste_count_spin.setValue(getattr(self.settings, 'paste_all_count', 0))
        self.paste_count_spin.blockSignals(False)

        rules = self.db.get_tab_rules()
        self.app_detector.set_rules(rules)
        self._refresh_ui_text()

    def _refresh_ui_text(self):
        self._settings_btn.setToolTip(t("settings"))
        self.search_bar.setPlaceholderText(t("search_placeholder"))
        self.mode_btn.setToolTip(t("picking_style"))
        self.strip_btn.setToolTip(t("strip_formatting"))
        self.enter_btn.setToolTip(t("auto_enter"))
        self.tab_btn.setToolTip(t("auto_tab"))
        self._reset_btn.setToolTip(t("reset_queue"))
        self.pin_filter_btn.setToolTip(t("pin_filter"))
        self.ghost_btn.setToolTip(t("ghost_mode"))
        self._clear_btn.setToolTip(t("clear_tab"))
        self._empty_text.setText(t("empty_title") + "\n" + t("empty_subtitle"))
        self.status_label.setText(t("ready"))
        self._update_count()
        if self._all_collapsed:
            self.collapse_all_btn.setToolTip(t("collapse_all"))
        else:
            self.collapse_all_btn.setToolTip(t("expand_all"))
        if hasattr(self, '_tray_show_action'):
            self._tray_show_action.setText(t("tray_show"))
            self._tray_ghost_action.setText(t("tray_ghost"))
            self._tray_settings_action.setText(t("tray_settings"))
            self._tray_quit_action.setText(t("tray_quit"))
        self._load_items()

    # ═══════════════════════════════════════════════════
    #  SYSTEM TRAY
    # ═══════════════════════════════════════════════════
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        app_icon = QApplication.instance().windowIcon()
        if app_icon.isNull():
            pix = QPixmap(32, 32)
            pix.fill(QColor(0, 0, 0, 0))
            painter = QPainter(pix)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(79, 124, 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
            painter.setPen(QColor(255, 255, 255))
            font = QFont(FONT_FAMILY, 14, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "C")
            painter.end()
            app_icon = QIcon(pix)
        self.tray_icon.setIcon(app_icon)
        self.tray_icon.setToolTip(APP_NAME)

        tray_menu = QMenu()
        self._tray_show_action = QAction(t("tray_show"), self)
        self._tray_show_action.triggered.connect(self._animate_show)
        tray_menu.addAction(self._tray_show_action)

        ghost_action = QAction(t("tray_ghost"), self)
        ghost_action.setCheckable(True)
        ghost_action.setChecked(self._ghost_mode)
        ghost_action.triggered.connect(self._toggle_ghost_mode)
        tray_menu.addAction(ghost_action)
        self._tray_ghost_action = ghost_action

        tray_menu.addSeparator()

        self._tray_settings_action = QAction(t("tray_settings"), self)
        self._tray_settings_action.triggered.connect(self._open_settings)
        tray_menu.addAction(self._tray_settings_action)

        tray_menu.addSeparator()

        self._tray_quit_action = QAction(t("tray_quit"), self)
        self._tray_quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(self._tray_quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

        # 4.3 — Rebuild tray menu on each right-click so last 5 items are fresh
        tray_menu.aboutToShow.connect(self._rebuild_tray_menu)
        self._tray_menu = tray_menu

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self._animate_hide()
            else:
                self._animate_show()

    def _minimize_to_tray(self):
        self._animate_hide()

    def _quit_app(self):
        self.settings.window_x = self.x()
        self.settings.window_y = self.y()
        self.settings.window_width = self.width()
        self.settings.window_height = self.height()
        self.db.save_all_settings(self.settings)
        self._hotkey_mgr.unregister_all()
        self.monitor.stop()
        self.hud.close()
        self.tray_icon.hide()
        self.db.close()
        QApplication.quit()

    # ═══════════════════════════════════════════════════
    #  UTILITIES
    # ═══════════════════════════════════════════════════
    def _center_on_screen(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - 20
            y = (geo.height() - self.height()) // 2 + geo.top()
            self.move(x, y)

    def _enable_blur(self):
        try:
            hwnd = int(self.winId())
            from cyberclip.utils.win32_helpers import enable_blur
            enable_blur(hwnd)
        except Exception:
            pass

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        if key == Qt.Key.Key_Escape:
            if self._paste_all_active:
                self._paste_all_active = False
                self.status_label.setText(t("paste_all_stopped"))
                self.hud.notify(t("paste_all_stopped"), 2000)
                QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))
            else:
                self._animate_hide()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            selected = self._get_selected_item()
            if selected:
                self._paste_item(selected)
            return

        if key == Qt.Key.Key_Delete and not (mods & Qt.KeyboardModifier.ControlModifier):
            selected = self._get_selected_item()
            if selected:
                self._delete_item(selected)
            return

        if key == Qt.Key.Key_D and mods & Qt.KeyboardModifier.ControlModifier:
            selected = self._get_selected_item()
            if selected:
                self._delete_item(selected)
            return

        if key == Qt.Key.Key_P and mods & Qt.KeyboardModifier.ControlModifier:
            selected = self._get_selected_item()
            if selected:
                self._toggle_pin(selected)
            return

        if key == Qt.Key.Key_Delete and mods & Qt.KeyboardModifier.ControlModifier:
            self._clear_tab()
            return

        if key == Qt.Key.Key_N and mods & Qt.KeyboardModifier.ControlModifier:
            self._fire_magazine()
            return

        if key == Qt.Key.Key_F and mods & Qt.KeyboardModifier.ControlModifier:
            self.search_bar.setFocus()
            self.search_bar.selectAll()
            return

        if key == Qt.Key.Key_G and mods & Qt.KeyboardModifier.ControlModifier:
            self._toggle_ghost_mode()
            return

        if key == Qt.Key.Key_Up:
            self._select_prev_item()
            return
        if key == Qt.Key.Key_Down:
            self._select_next_item()
            return

        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9 and mods & Qt.KeyboardModifier.ControlModifier:
            idx = key - Qt.Key.Key_1
            if idx < len(self._item_widgets):
                self._paste_item(self._item_widgets[idx].item)
            return

        super().keyPressEvent(event)

    def _get_selected_item(self):
        for w in self._item_widgets:
            if w._selected:
                return w.item
        if self._item_widgets:
            return self._item_widgets[0].item
        return None

    def _select_prev_item(self):
        if not self._item_widgets:
            return
        current_idx = next((i for i, w in enumerate(self._item_widgets) if w._selected), -1)
        new_idx = max(0, current_idx - 1)
        for w in self._item_widgets:
            w.set_selected(False)
        self._item_widgets[new_idx].set_selected(True)
        self._ensure_visible(self._item_widgets[new_idx])

    def _select_next_item(self):
        if not self._item_widgets:
            return
        current_idx = next((i for i, w in enumerate(self._item_widgets) if w._selected), -1)
        new_idx = min(len(self._item_widgets) - 1, current_idx + 1)
        for w in self._item_widgets:
            w.set_selected(False)
        self._item_widgets[new_idx].set_selected(True)
        self._ensure_visible(self._item_widgets[new_idx])

    def _ensure_visible(self, widget):
        self.scroll_area.ensureWidgetVisible(widget, 50, 50)

    def closeEvent(self, event):
        event.ignore()
        self._minimize_to_tray()

    # ═══════════════════════════════════════════════════
    #  PHASE 4.3 — Dynamic tray menu with last 5 items
    # ═══════════════════════════════════════════════════
    def _rebuild_tray_menu(self):
        """Rebuild the tray context menu with current last 5 items."""
        menu = self._tray_menu
        menu.clear()

        menu.addAction(t("tray_show"), self._animate_show)

        ghost_action = menu.addAction(t("tray_ghost"))
        ghost_action.setCheckable(True)
        ghost_action.setChecked(self._ghost_mode)
        ghost_action.triggered.connect(self._toggle_ghost_mode)
        self._tray_ghost_action = ghost_action

        menu.addSeparator()

        # Last 5 recent items for quick paste
        recent = self.db.get_items(self._current_tab, limit=5)
        if recent:
            recent_menu = menu.addMenu(t("tray_recent"))
            for item in recent:
                label = (item.preview or "")[:50].replace('\n', ' ')
                action = recent_menu.addAction(label)
                action.triggered.connect(lambda checked, i=item: self._paste_item(i))

        menu.addSeparator()
        menu.addAction(t("tray_settings"), self._open_settings)
        menu.addSeparator()
        menu.addAction(t("tray_quit"), self._quit_app)

    # ═══════════════════════════════════════════════════
    #  PHASE 2.2 — Tray icon ghost mode indicator
    # ═══════════════════════════════════════════════════
    def _update_tray_icon(self):
        """Change tray icon color to show ghost mode state."""
        pix = QPixmap(32, 32)
        pix.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Ghost mode = dim gray; normal = accent blue
        color = QColor(100, 100, 110) if self._ghost_mode else QColor(79, 124, 255)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
        painter.setPen(QColor(255, 255, 255))
        font = QFont(FONT_FAMILY, 14, QFont.Weight.Bold)
        painter.setFont(font)
        label_text = "G" if self._ghost_mode else "C"
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, label_text)
        painter.end()
        self.tray_icon.setIcon(QIcon(pix))

    # ═══════════════════════════════════════════════════
    #  PHASE 5.1 — Quick Paste Popup
    # ═══════════════════════════════════════════════════
    def _show_quick_paste_popup(self):
        """Open the quick paste popup at the current cursor position."""
        from cyberclip.gui.quick_paste_popup import QuickPastePopup
        if self._quick_paste_popup is None:
            self._quick_paste_popup = QuickPastePopup()
            self._quick_paste_popup.paste_requested.connect(self._paste_item)
        items = self.db.get_items(limit=QUICK_PASTE_MAX_ITEMS)
        self._quick_paste_popup.show_at_cursor(items)

    # ═══════════════════════════════════════════════════
    #  PHASE 5.2 — Text Transforms
    # ═══════════════════════════════════════════════════
    @pyqtSlot(ClipboardItem, str)
    def _on_transform_requested(self, item: ClipboardItem, transform_key: str):
        """Apply a text transform and add the result as a new clip."""
        from cyberclip.utils.text_transforms import apply as apply_transform
        new_text = apply_transform(transform_key, item.text_content)
        if new_text == item.text_content:
            return  # no change
        new_item = ClipboardItem(
            content_type=item.content_type,
            text_content=new_text,
            source_app="CyberClip (transform)",
            tab=item.tab,
        )
        # 1.6 — suppress before writing to clipboard
        self.monitor.suppress_next()
        self.db.add_item(new_item, max_items=getattr(self.settings, 'max_items', 200))
        if new_item.tab == self._current_tab:
            self._add_item_widget(new_item, animate=True)
            self._update_empty_state()
            self._update_count()
        QApplication.clipboard().setText(new_text)
        self.status_label.setText(f"✓ Transform: {transform_key.replace('transform_', '')}")
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    # ═══════════════════════════════════════════════════
    #  PHASE 5.4 — Save as Snippet
    # ═══════════════════════════════════════════════════
    @pyqtSlot(ClipboardItem)
    def _on_save_snippet(self, item: ClipboardItem):
        """Prompt for snippet name and trigger, then save."""
        from PyQt6.QtWidgets import QInputDialog
        from cyberclip.storage.models import Snippet
        name, ok = QInputDialog.getText(self, t("snippet_name"), t("snippet_name") + ":")
        if not ok or not name.strip():
            return
        trigger, ok2 = QInputDialog.getText(self, t("snippet_trigger"), t("snippet_trigger") + ":")
        if not ok2 or not trigger.strip():
            return
        snippet = Snippet(name=name.strip(), trigger=trigger.strip().lower(),
                          content=item.text_content)
        self.db.add_snippet(snippet)
        self.status_label.setText(t("snippet_saved"))
        QTimer.singleShot(2000, lambda: self.status_label.setText(t("ready")))

    # ═══════════════════════════════════════════════════
    #  PHASE 5.5 — Export / Import
    # ═══════════════════════════════════════════════════
    def _export_history(self):
        import json, base64
        from datetime import datetime as dt
        path, _ = QFileDialog.getSaveFileName(
            self, t("export_history"), "cyberclip_export.json", "JSON Files (*.json)"
        )
        if not path:
            return
        items = self.db.get_items(limit=10000)
        clips = []
        for item in items:
            entry = {
                "content": item.text_content,
                "type": item.content_type,
                "created_at": item.created_at,
                "is_pinned": item.pinned,
                "is_sensitive": item.is_sensitive,
                "tab": item.tab,
            }
            if item.image_path and os.path.exists(item.image_path):
                with open(item.image_path, "rb") as f:
                    entry["image_b64"] = base64.b64encode(f.read()).decode("ascii")
            clips.append(entry)
        export_data = {
            "version": "1.0",
            "exported_at": dt.now().isoformat(),
            "clips": clips,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        self.status_label.setText(t("export_done", count=len(clips)))
        QTimer.singleShot(3000, lambda: self.status_label.setText(t("ready")))

    def _import_history(self):
        import json, base64, tempfile, os
        path, _ = QFileDialog.getOpenFileName(
            self, t("import_history"), "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.status_label.setText(t("db_error"))
            return
        clips = data.get("clips", [])
        imported, skipped = 0, 0
        for entry in clips:
            text = entry.get("content", "")
            ctype = entry.get("type", "text")
            tab = entry.get("tab", "General")
            if self.db.item_exists(text, tab):
                skipped += 1
                continue
            image_path = ""
            if "image_b64" in entry:
                try:
                    img_data = base64.b64decode(entry["image_b64"])
                    image_path = self.image_store.save_bytes(img_data)
                except Exception:
                    pass
            item = ClipboardItem(
                content_type=ctype,
                text_content=text,
                image_path=image_path,
                tab=tab,
                pinned=entry.get("is_pinned", False),
                created_at=entry.get("created_at", ""),
                is_sensitive=entry.get("is_sensitive", False),
            )
            self.db.add_item(item, max_items=getattr(self.settings, 'max_items', 200))
            imported += 1
        self._load_items()
        self.status_label.setText(t("import_done", count=imported, skipped=skipped))
        QTimer.singleShot(3000, lambda: self.status_label.setText(t("ready")))
