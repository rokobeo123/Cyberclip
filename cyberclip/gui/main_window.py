"""Main CyberClip window - modern clipboard manager UI."""
import os
import subprocess
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QScrollArea, QApplication,
    QSizePolicy, QSystemTrayIcon, QMenu, QGraphicsOpacityEffect,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtSlot, QTimer, QPropertyAnimation,
    QEasingCurve, QPoint, QSize, QEvent, QRect,
    QParallelAnimationGroup, QMimeData,
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QColor, QPainter, QPen, QBrush, QImage,
    QLinearGradient, QFont, QAction, QCursor, QGuiApplication,
    QShortcut, QKeySequence,
)

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
    TYPE_URL, TYPE_FILE, TYPE_COLOR, DEFAULT_BLACKLIST, DEFAULT_HOTKEYS,
    TEXT_SECONDARY, ACCENT, ANIM_FAST, ANIM_NORMAL,
)
from cyberclip.core.global_hotkeys import GlobalHotkeyManager


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
    ICON_COLLAPSE_ALL = "\uf066"  # compress
    ICON_EXPAND_ALL = "\uf065"    # expand

    def __init__(self):
        super().__init__()
        # Remove native title bar, add frameless + translucent
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("CyberClipMain")
        self.setMinimumSize(380, 500)

        # Initialize subsystems
        self.db = Database()
        self.image_store = ImageStore()
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
        self._target_hwnd = None  # foreground window to paste into
        self._paste_busy = False  # lock to prevent rapid paste skipping
        self._paste_queued = 0   # queued paste count from rapid key spam
        self._paste_all_active = False  # paste-all queue mode

        # Clipboard monitor (create before UI setup so _apply_settings works)
        self.monitor = ClipboardMonitor(self.image_store)
        self.monitor.item_captured.connect(self._on_item_captured)

        # Build UI
        self._setup_ui()
        self._apply_settings()
        self._load_items()

        # HUD (toast notifications — starts hidden)
        self.hud = HUDWidget()

        # App detector timer
        self._app_timer = QTimer(self)
        self._app_timer.timeout.connect(self._check_app_switch)
        self._app_timer.start(1000)

        # Magazine signals
        self.magazine.queue_changed.connect(self._on_queue_changed)

        # System tray
        self._setup_tray()

        # Global hotkeys
        self._setup_global_hotkeys()

        # Window position
        if self.settings.window_x >= 0:
            self.move(self.settings.window_x, self.settings.window_y)
            self.resize(self.settings.window_width, self.settings.window_height)
        else:
            self.resize(420, 680)
            self._center_on_screen()

        # Enable DWM blur on Win11
        QTimer.singleShot(100, self._enable_blur)

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
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

        # App icon/title
        title_label = QLabel(APP_NAME)
        title_label.setObjectName("TitleLabel")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        # Ghost mode indicator
        self.ghost_indicator = QLabel("\uf21b  GHOST")
        self.ghost_indicator.setObjectName("GhostIndicator")
        self.ghost_indicator.setVisible(self._ghost_mode)
        tb_layout.addWidget(self.ghost_indicator)

        # Title buttons
        settings_btn = QPushButton(self.ICON_SETTINGS)
        settings_btn.setObjectName("TitleButton")
        settings_btn.setFixedSize(32, 28)
        settings_btn.setToolTip("Cài đặt")
        settings_btn.clicked.connect(self._open_settings)
        tb_layout.addWidget(settings_btn)

        min_btn = QPushButton(self.ICON_MINIMIZE)
        min_btn.setObjectName("TitleButton")
        min_btn.setFixedSize(32, 28)
        min_btn.setToolTip("Thu nhỏ")
        min_btn.clicked.connect(self._minimize_to_tray)
        tb_layout.addWidget(min_btn)

        close_btn = QPushButton(self.ICON_CLOSE)
        close_btn.setObjectName("CloseButton")
        close_btn.setFixedSize(32, 28)
        close_btn.setToolTip("Đóng")
        close_btn.clicked.connect(self._minimize_to_tray)
        tb_layout.addWidget(close_btn)

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
        self.search_bar.setPlaceholderText("Tìm kiếm lịch sử…")
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

        # FIFO/LIFO toggle
        self.mode_btn = QPushButton(self.ICON_FIFO + "  FIFO")
        self.mode_btn.setObjectName("ToolButton")
        self.mode_btn.setCheckable(True)
        self.mode_btn.setToolTip("Chuyển FIFO/LIFO")
        self.mode_btn.clicked.connect(self._toggle_mode)
        tb2_layout.addWidget(self.mode_btn)

        # Strip formatting toggle
        self.strip_btn = QPushButton(self.ICON_STRIP + "  Clean")
        self.strip_btn.setObjectName("ToolButton")
        self.strip_btn.setCheckable(True)
        self.strip_btn.setChecked(self.settings.strip_formatting)
        self.strip_btn.setToolTip("Xóa định dạng khi dán")
        self.strip_btn.clicked.connect(self._toggle_strip)
        tb2_layout.addWidget(self.strip_btn)

        # Auto-enter toggle
        self.enter_btn = QPushButton(self.ICON_ENTER + "  Auto↵")
        self.enter_btn.setObjectName("ToolButton")
        self.enter_btn.setCheckable(True)
        self.enter_btn.setChecked(self.settings.auto_enter)
        self.enter_btn.setToolTip("Tự động nhấn Enter sau dán")
        self.enter_btn.clicked.connect(self._toggle_auto_enter)
        tb2_layout.addWidget(self.enter_btn)

        tb2_layout.addStretch()

        # Reset queue button
        reset_btn = QPushButton("\uf0e2")  # rotate-left icon
        reset_btn.setObjectName("ToolButton")
        reset_btn.setToolTip("Đặt lại hàng đợi")
        reset_btn.clicked.connect(self._reset_magazine)
        tb2_layout.addWidget(reset_btn)

        # Pinned filter
        self.pin_filter_btn = QPushButton(self.ICON_PIN_MENU)
        self.pin_filter_btn.setObjectName("ToolButton")
        self.pin_filter_btn.setCheckable(True)
        self.pin_filter_btn.setToolTip("Chỉ hiện đã ghim")
        self.pin_filter_btn.clicked.connect(self._toggle_pin_filter)
        tb2_layout.addWidget(self.pin_filter_btn)

        # Collapse all button
        self._all_collapsed = False
        self.collapse_all_btn = QPushButton(self.ICON_EXPAND_ALL)
        self.collapse_all_btn.setObjectName("ToolButton")
        self.collapse_all_btn.setToolTip("Mở rộng tất cả")
        self.collapse_all_btn.clicked.connect(self._toggle_collapse_all)
        tb2_layout.addWidget(self.collapse_all_btn)

        # Ghost mode toggle
        self.ghost_btn = QPushButton(self.ICON_GHOST)
        self.ghost_btn.setObjectName("ToolButton")
        self.ghost_btn.setCheckable(True)
        self.ghost_btn.setChecked(self._ghost_mode)
        self.ghost_btn.setToolTip("Chế độ ẩn - tạm dừng ghi")
        self.ghost_btn.clicked.connect(self._toggle_ghost_mode)
        tb2_layout.addWidget(self.ghost_btn)

        # Clear button
        clear_btn = QPushButton(self.ICON_CLEAR)
        clear_btn.setObjectName("ToolButton")
        clear_btn.setProperty("danger", True)
        clear_btn.setToolTip("Xóa mục chưa ghim")
        clear_btn.clicked.connect(self._clear_tab)
        tb2_layout.addWidget(clear_btn)

        main_layout.addWidget(toolbar)

        # ── Clip List (Scroll Area) ──
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
        empty_text = QLabel("Chưa có mục nào\nSao chép gì đó để bắt đầu")
        empty_text.setObjectName("EmptyState")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_text)
        self.list_layout.addWidget(self.empty_widget)

        # ── Status Bar ──
        status_bar = QWidget()
        status_bar.setObjectName("StatusBar")
        status_bar.setFixedHeight(30)
        sb_layout = QHBoxLayout(status_bar)
        sb_layout.setContentsMargins(12, 0, 12, 0)

        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setObjectName("StatusLabel")
        sb_layout.addWidget(self.status_label)

        sb_layout.addStretch()

        self.magazine_label = QLabel("")
        self.magazine_label.setObjectName("MagazineCounter")
        sb_layout.addWidget(self.magazine_label)

        self.count_label = QLabel("0 mục")
        self.count_label.setObjectName("StatusLabel")
        sb_layout.addWidget(self.count_label)

        main_layout.addWidget(status_bar)

    # ═══════════════════════════════════════════════════
    #  PAINTING - Clean rounded dark window
    # ═══════════════════════════════════════════════════
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)

        # Clean dark background with subtle border
        painter.setBrush(QColor(28, 28, 30, 248))
        pen = QPen(QColor(255, 255, 255, 18))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 14, 14)

        painter.end()

    # ═══════════════════════════════════════════════════
    #  WINDOW EDGE RESIZE (mouse-based for frameless window)
    # ═══════════════════════════════════════════════════
    _RESIZE_BORDER = 8

    def _edge_zone(self, pos):
        """Return resize edge/corner or None for a given local pos."""
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
        "l": Qt.CursorShape.SizeHorCursor,
        "r": Qt.CursorShape.SizeHorCursor,
        "t": Qt.CursorShape.SizeVerCursor,
        "b": Qt.CursorShape.SizeVerCursor,
        "tl": Qt.CursorShape.SizeFDiagCursor,
        "br": Qt.CursorShape.SizeFDiagCursor,
        "tr": Qt.CursorShape.SizeBDiagCursor,
        "bl": Qt.CursorShape.SizeBDiagCursor,
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

            if "r" in edge:
                geo.setRight(geo.right() + delta.x())
            if "b" in edge:
                geo.setBottom(geo.bottom() + delta.y())
            if "l" in edge:
                geo.setLeft(min(geo.left() + delta.x(), geo.right() - min_w))
            if "t" in edge:
                geo.setTop(min(geo.top() + delta.y(), geo.bottom() - min_h))

            if geo.width() >= min_w and geo.height() >= min_h:
                self.setGeometry(geo)
            event.accept()
            return

        # Update cursor when hovering over edges
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

    # ═══════════════════════════════════════════════════
    #  TITLE BAR DRAG
    # ═══════════════════════════════════════════════════
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
        # Assign tab based on app detection
        tab = self.app_detector.detect_tab()
        item.tab = tab or self._current_tab

        # Skip exact duplicate if the most recent item has the same content
        if item.content_type != TYPE_IMAGE and self._item_widgets:
            latest = self._item_widgets[0].item
            if latest.text_content == item.text_content and latest.content_type == item.content_type:
                return

        # Save to DB
        self.db.add_item(item)
        self.magazine.add(item)

        # Add to UI if matching current tab
        if item.tab == self._current_tab or not self._current_tab:
            self._add_item_widget(item, animate=True)
            self._update_empty_state()
            self._update_count()

        # Update tabs
        tabs = self.db.get_tabs()
        self.tab_bar.set_tabs(tabs)

        # Toast notification
        self.hud.notify(f"Đã sao chép: {item.preview[:30]}", 2000)

        self.status_label.setText(f"Đã sao chép: {item.content_type}")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _load_items(self):
        # Clear existing
        for w in self._item_widgets:
            w.deleteLater()
        self._item_widgets.clear()

        if self._search_query:
            items = self.db.search_items(self._search_query, self._current_tab)
        else:
            items = self.db.get_items(self._current_tab)

        # Apply pin filter
        if self._pin_filter:
            items = [i for i in items if i.pinned]

        # Load into magazine
        fifo_items = self.db.get_items_fifo(self._current_tab)
        self.magazine.load(fifo_items)

        for i, item in enumerate(items):
            self._add_item_widget(item, animate=False)

        self._update_empty_state()
        self._update_count()
        self._highlight_magazine_item()

        tabs = self.db.get_tabs()
        self.tab_bar.set_tabs(tabs)

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

        # Insert at top (newest first)
        self.list_layout.insertWidget(0, widget)
        self._item_widgets.insert(0, widget)

        if animate:
            widget.animate_in(delay_ms=0)

    def _update_empty_state(self):
        has_items = len(self._item_widgets) > 0
        self.empty_widget.setVisible(not has_items)

    def _update_count(self):
        count = len(self._item_widgets)
        self.count_label.setText(f"{count} mục")

    # ═══════════════════════════════════════════════════
    #  ITEM ACTIONS
    # ═══════════════════════════════════════════════════
    @pyqtSlot(ClipboardItem)
    def _paste_item(self, item: ClipboardItem):
        """Copy item to clipboard so user can paste it anywhere."""
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

        # Delay resume to avoid re-capturing our own clipboard change
        QTimer.singleShot(500, self.monitor.resume)

        # Status feedback
        self.status_label.setText("✓ Đã sao chép — Ctrl+V để dán")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _sequential_paste(self):
        """The CORE feature: paste current magazine item into the target app,
        then auto-advance to the next item.  Triggered by global hotkey.
        
        If already pasting, queues the request so rapid Ctrl+Shift+V spam works.
        """
        if self._paste_busy:
            self._paste_queued += 1
            return

        item = self.magazine.fire()
        if not item:
            self._paste_queued = 0
            return

        self._paste_busy = True
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

        # Highlight current item in list
        self._highlight_magazine_item()

        # Inject Ctrl+V after a short delay for clipboard sync
        QTimer.singleShot(30, self._do_inject_paste)

    @pyqtSlot(ClipboardItem)
    def _paste_and_inject(self, item: ClipboardItem):
        """Copy item to clipboard then simulate Ctrl+V into the target window."""
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

        # Hide window so paste goes to the window behind us
        if self.isVisible():
            self.hide()
        QTimer.singleShot(100, self._do_inject_paste)

    def _do_inject_paste(self):
        """Inject Ctrl+V into whatever window is currently focused."""
        from cyberclip.utils.win32_helpers import (
            send_ctrl_v_fast, send_key, VK_RETURN, VK_TAB, KEYEVENTF_KEYUP,
        )
        import time

        send_ctrl_v_fast()

        # Auto-movement after paste
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

    def _after_paste(self):
        # Don't resume monitoring immediately — give clipboard time to settle
        QTimer.singleShot(200, self.monitor.resume)
        self._paste_busy = False  # release lock
        peek = self.magazine.peek()
        if peek:
            msg = f"✓ Đã dán — tiếp: {peek.preview[:30]}"
        else:
            msg = "✓ Đã dán — hết hàng đợi"
        self.hud.notify(msg, 2000)
        self.status_label.setText(msg)
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

        # Drain queued paste requests (from rapid Ctrl+Shift+V spam)
        if self._paste_queued > 0:
            self._paste_queued -= 1
            QTimer.singleShot(20, self._sequential_paste)
        elif self._paste_all_active and peek:
            QTimer.singleShot(100, self._sequential_paste)
        elif self._paste_all_active and not peek:
            self._paste_all_active = False

    def _highlight_magazine_item(self):
        """Highlight the current magazine item in the item list."""
        current = self.magazine.peek()
        for w in self._item_widgets:
            is_current = (current is not None) and (w.item.id == current.id)
            w.set_magazine_active(is_current)

    @pyqtSlot(ClipboardItem)
    def _delete_item(self, item: ClipboardItem):
        # Find widget
        for w in self._item_widgets:
            if w.item.id == item.id:
                self._item_widgets.remove(w)
                w.animate_out(callback=lambda: self._finalize_delete(w, item))
                break

    def _finalize_delete(self, widget, item):
        self.db.delete_item(item.id)
        if item.image_path:
            self.image_store.delete_image(item.image_path)
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

    @pyqtSlot(ClipboardItem)
    def _ocr_item(self, item: ClipboardItem):
        self.status_label.setText("Đang quét văn bản (OCR)…")
        QTimer.singleShot(100, lambda: self._do_ocr(item))

    def _do_ocr(self, item: ClipboardItem):
        from cyberclip.core.ocr_scanner import scan_image
        text = scan_image(item.image_path)
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText(f"OCR: {len(text)} ký tự được trích xuất")
        else:
            self.status_label.setText("OCR: Không tìm thấy văn bản")
        QTimer.singleShot(3000, lambda: self.status_label.setText("Sẵn sàng"))

    @pyqtSlot(str)
    def _open_file(self, path: str):
        if os.path.exists(path):
            if os.path.isdir(path):
                subprocess.Popen(f'explorer "{path}"')
            else:
                subprocess.Popen(f'explorer /select,"{path}"')

    @pyqtSlot(ClipboardItem)
    def _view_image(self, item: ClipboardItem):
        """Open the image viewer dialog for an image clip."""
        from cyberclip.gui.image_viewer import ImageViewerDialog
        if item.image_path and os.path.exists(item.image_path):
            viewer = ImageViewerDialog(item.image_path, self)
            viewer.exec()

    @pyqtSlot(ClipboardItem)
    def _on_item_clicked(self, item: ClipboardItem):
        """Single click sets this item as the magazine start position."""
        for w in self._item_widgets:
            w.set_selected(w.item.id == item.id)
        # Set magazine to start from this item
        if self.magazine.set_start(item.id):
            self._highlight_magazine_item()
            peek = self.magazine.peek()
            if peek:
                self.status_label.setText(f"▶ Bắt đầu từ: {peek.preview[:40]}")
                QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    @pyqtSlot(ClipboardItem)
    def _start_from_here(self, item: ClipboardItem):
        """Context menu start from here — same as click."""
        self._on_item_clicked(item)

    # ── Drag & Drop reordering ──
    def _list_drag_enter(self, event):
        if event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            event.acceptProposedAction()

    def _list_drag_move(self, event):
        if event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            event.acceptProposedAction()
            # Highlight drop target
            target_idx = self._drop_index_at(event.position().toPoint())
            for i, w in enumerate(self._item_widgets):
                w.setProperty("drop_target", "true" if i == target_idx else "false")
                w.style().unpolish(w)
                w.style().polish(w)

    def _list_drop(self, event):
        if not event.mimeData().hasFormat("application/x-cyberclip-item-id"):
            return
        # Clear drop highlights
        for w in self._item_widgets:
            w.setProperty("drop_target", "false")
            w.style().unpolish(w)
            w.style().polish(w)

        dragged_id = int(event.mimeData().data(
            "application/x-cyberclip-item-id").data().decode())
        target_idx = self._drop_index_at(event.position().toPoint())

        # Find the dragged widget
        dragged_widget = None
        dragged_idx = -1
        for i, w in enumerate(self._item_widgets):
            if w.item.id == dragged_id:
                dragged_widget = w
                dragged_idx = i
                break
        if dragged_widget is None or dragged_idx == target_idx:
            return

        # Move widget in internal list
        self._item_widgets.pop(dragged_idx)
        if target_idx > dragged_idx:
            target_idx -= 1
        target_idx = max(0, min(target_idx, len(self._item_widgets)))
        self._item_widgets.insert(target_idx, dragged_widget)

        # Rebuild the layout to match new order
        # Remove all widgets from layout (without deleting)
        while self.list_layout.count():
            self.list_layout.takeAt(0)
        for w in self._item_widgets:
            self.list_layout.addWidget(w)
        # Re-add empty state widget at the end (always present but hidden)
        self.list_layout.addWidget(self.empty_widget)

        # Sync magazine order
        new_ids = [w.item.id for w in self._item_widgets]
        self.magazine.reorder(new_ids)
        self._highlight_magazine_item()

        event.acceptProposedAction()

    def _drop_index_at(self, pos):
        """Determine the list index at the given position for drop insertion."""
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
        """Fire magazine — paste current item and auto-advance."""
        self._sequential_paste()

    def _paste_all(self):
        """Paste ALL remaining items in the queue sequentially."""
        if self._paste_busy or self._paste_all_active:
            # Stop if already running
            self._paste_all_active = False
            self.status_label.setText("⏹ Dừng dán hàng loạt")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))
            return
        if not self.magazine.peek():
            self.status_label.setText("⚠ Hàng đợi trống")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))
            return
        self._paste_all_active = True
        remaining = self.magazine.remaining
        self.hud.notify(f"▶ Dán hàng loạt: {remaining} mục", 3000)
        self._sequential_paste()

    def _skip_magazine(self):
        """Skip current magazine item without pasting."""
        item = self.magazine.fire()
        if item:
            self._highlight_magazine_item()
            peek = self.magazine.peek()
            if peek:
                self.status_label.setText(f"⏭ Bỏ qua — tiếp: {peek.preview[:40]}")
            else:
                self.status_label.setText("⏭ Bỏ qua — hết hàng đợi")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))
        else:
            self.status_label.setText("⚠ Hàng đợi trống")
            QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    @pyqtSlot(int, int)
    def _on_queue_changed(self, index, total):
        if total > 0 and index < total:
            self.magazine_label.setText(f"▶ {index+1}/{total}")
        elif total > 0 and index >= total:
            self.magazine_label.setText(f"✓ {total}/{total}")
        else:
            self.magazine_label.setText("")
        peek = self.magazine.peek()
        self.hud.update_info(index, total, peek.preview if peek else "")
        self._highlight_magazine_item()

    # ═══════════════════════════════════════════════════
    #  GLOBAL HOTKEYS
    # ═══════════════════════════════════════════════════
    def _setup_global_hotkeys(self):
        """Register all global hotkeys from settings."""
        self._hotkey_mgr = GlobalHotkeyManager(self)
        self._hotkey_mgr.triggered.connect(self._on_global_hotkey)

        # Start with defaults, overlay user overrides for matching keys only
        hotkeys = dict(DEFAULT_HOTKEYS)
        if self.settings.hotkeys:
            for k, v in self.settings.hotkeys.items():
                if k in hotkeys:
                    hotkeys[k] = v
        self.settings.hotkeys = hotkeys

        for action, shortcut in hotkeys.items():
            ok = self._hotkey_mgr.register(action, shortcut)
            if not ok:
                print(f"[CyberClip] Failed to register hotkey: {action} = {shortcut}")

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

    def _reload_hotkeys(self):
        """Re-register hotkeys after user changes them in settings."""
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
        self.db.save_all_settings(self.settings)

    def _toggle_ghost_mode(self):
        self._ghost_mode = not self._ghost_mode
        self.settings.ghost_mode = self._ghost_mode
        self.monitor.set_ghost_mode(self._ghost_mode)
        self.ghost_indicator.setVisible(self._ghost_mode)
        self.ghost_btn.setChecked(self._ghost_mode)
        self.hud.set_ghost_mode(self._ghost_mode)
        self.db.save_all_settings(self.settings)

        self.status_label.setText("Chế độ ẩn: BẬT" if self._ghost_mode else "Chế độ ẩn: TẮT")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _clear_tab(self):
        self.db.clear_tab(self._current_tab)
        self._load_items()
        self.status_label.setText(f"Đã xóa: {self._current_tab}")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _reset_magazine(self):
        """Reset magazine: re-sort according to current FIFO/LIFO mode and start from beginning."""
        self.magazine.reset()
        self._highlight_magazine_item()
        mode_name = "FIFO" if self.settings.picking_style == "FIFO" else "LIFO"
        self.status_label.setText(f"▶ Đặt lại hàng đợi ({mode_name})")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _toggle_pin_filter(self):
        """Toggle showing only pinned items."""
        self._pin_filter = self.pin_filter_btn.isChecked()
        self._load_items()
        if self._pin_filter:
            self.status_label.setText("Chỉ hiện mục đã ghim")
        else:
            self.status_label.setText("Hiện tất cả")
        QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))

    def _toggle_collapse_all(self):
        """Toggle expand/collapse all clip items."""
        self._all_collapsed = not self._all_collapsed
        for w in self._item_widgets:
            if self._all_collapsed and not w._collapsed:
                w._toggle_collapse()
            elif not self._all_collapsed and w._collapsed:
                w._toggle_collapse()
        if self._all_collapsed:
            # All expanded now — button says "collapse all"
            self.collapse_all_btn.setText(self.ICON_COLLAPSE_ALL)
            self.collapse_all_btn.setToolTip("Thu gọn tất cả")
        else:
            # All collapsed now — button says "expand all"
            self.collapse_all_btn.setText(self.ICON_EXPAND_ALL)
            self.collapse_all_btn.setToolTip("Mở rộng tất cả")

    # ═══════════════════════════════════════════════════
    #  SEARCH
    # ═══════════════════════════════════════════════════
    def _on_search(self, text: str):
        self._search_query = text.strip()
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
        self.show()
        self.setWindowOpacity(0.0)

        group = QParallelAnimationGroup(self)

        # Fade in
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
        self.ghost_btn.setChecked(self.settings.ghost_mode)
        self.ghost_indicator.setVisible(self.settings.ghost_mode)

        # App detector rules
        rules = self.db.get_tab_rules()
        self.app_detector.set_rules(rules)

    # ═══════════════════════════════════════════════════
    #  SYSTEM TRAY
    # ═══════════════════════════════════════════════════
    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Generate a simple icon
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
        self.tray_icon.setIcon(QIcon(pix))
        self.tray_icon.setToolTip(APP_NAME)

        # Tray menu
        tray_menu = QMenu()
        show_action = QAction("Hiện CyberClip", self)
        show_action.triggered.connect(self._animate_show)
        tray_menu.addAction(show_action)

        ghost_action = QAction("Chế độ ẩn", self)
        ghost_action.setCheckable(True)
        ghost_action.setChecked(self._ghost_mode)
        ghost_action.triggered.connect(self._toggle_ghost_mode)
        tray_menu.addAction(ghost_action)
        self._tray_ghost_action = ghost_action

        tray_menu.addSeparator()

        settings_action = QAction("Cài đặt", self)
        settings_action.triggered.connect(self._open_settings)
        tray_menu.addAction(settings_action)

        tray_menu.addSeparator()

        quit_action = QAction("Thoát", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self._animate_hide()
            else:
                self._animate_show()

    def _minimize_to_tray(self):
        self._animate_hide()

    def _quit_app(self):
        # Save state
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

        # Escape — stop paste-all if active, otherwise hide window
        if key == Qt.Key.Key_Escape:
            if self._paste_all_active:
                self._paste_all_active = False
                self.status_label.setText("⏹ Đã dừng dán hàng loạt")
                self.hud.notify("⏹ Đã dừng dán hàng loạt", 2000)
                QTimer.singleShot(2000, lambda: self.status_label.setText("Sẵn sàng"))
            else:
                self._animate_hide()
            return

        # Enter — paste selected item (copy to clipboard)
        if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            selected = self._get_selected_item()
            if selected:
                self._paste_item(selected)
            return

        # Delete — delete selected item
        if key == Qt.Key.Key_Delete:
            selected = self._get_selected_item()
            if selected:
                self._delete_item(selected)
            return

        # Ctrl+D — delete selected item
        if key == Qt.Key.Key_D and mods & Qt.KeyboardModifier.ControlModifier:
            selected = self._get_selected_item()
            if selected:
                self._delete_item(selected)
            return

        # Ctrl+P — pin/unpin selected item
        if key == Qt.Key.Key_P and mods & Qt.KeyboardModifier.ControlModifier:
            selected = self._get_selected_item()
            if selected:
                self._toggle_pin(selected)
            return

        # Ctrl+Shift+Delete — clear all unpinned
        if key == Qt.Key.Key_Delete and mods & Qt.KeyboardModifier.ControlModifier:
            self._clear_tab()
            return

        # Ctrl+N — paste next from magazine (skip + paste)
        if key == Qt.Key.Key_N and mods & Qt.KeyboardModifier.ControlModifier:
            self._fire_magazine()
            return

        # Ctrl+F — focus search bar
        if key == Qt.Key.Key_F and mods & Qt.KeyboardModifier.ControlModifier:
            self.search_bar.setFocus()
            self.search_bar.selectAll()
            return

        # Ctrl+G — toggle ghost mode
        if key == Qt.Key.Key_G and mods & Qt.KeyboardModifier.ControlModifier:
            self._toggle_ghost_mode()
            return

        # Up/Down — navigate items
        if key == Qt.Key.Key_Up:
            self._select_prev_item()
            return
        if key == Qt.Key.Key_Down:
            self._select_next_item()
            return

        # 1-9 — quick paste item by position
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
        # If nothing selected, use the first item
        if self._item_widgets:
            return self._item_widgets[0].item
        return None

    def _select_prev_item(self):
        if not self._item_widgets:
            return
        current_idx = -1
        for i, w in enumerate(self._item_widgets):
            if w._selected:
                current_idx = i
                break
        new_idx = max(0, current_idx - 1)
        for w in self._item_widgets:
            w.set_selected(False)
        self._item_widgets[new_idx].set_selected(True)
        self._ensure_visible(self._item_widgets[new_idx])

    def _select_next_item(self):
        if not self._item_widgets:
            return
        current_idx = -1
        for i, w in enumerate(self._item_widgets):
            if w._selected:
                current_idx = i
                break
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
