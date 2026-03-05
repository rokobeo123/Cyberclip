# Modified: [5.1] New widget — frameless Quick Paste popup at cursor position.
#           Opens on Ctrl+Shift+Space, shows last 10 items, click or press 1-9 to paste.
#           Auto-closes after paste, Escape, or focus loss.
"""Quick Paste popup widget for CyberClip (Phase 5.1)."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QApplication,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPoint, QTimer, QSize,
)
from PyQt6.QtGui import QKeyEvent, QFocusEvent, QCursor

from cyberclip.storage.models import ClipboardItem
from cyberclip.utils.i18n import t
from cyberclip.utils.constants import (
    QUICK_PASTE_MAX_ITEMS, TYPE_IMAGE, DARK_BG, DARK_SURFACE,
    TEXT_PRIMARY, TEXT_SECONDARY, ACCENT, BORDER_DEFAULT,
)


class QuickPastePopup(QWidget):
    """
    Frameless popup that shows the most recent clipboard items.
    Emits ``paste_requested(item)`` when the user selects an item.
    """
    paste_requested = pyqtSignal(ClipboardItem)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self._items: list[ClipboardItem] = []
        self._setup_ui()
        self.setStyleSheet(self._stylesheet())

    # ── UI setup ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 8)
        layout.setSpacing(4)

        # Header
        header = QLabel(t("quick_paste_title"))
        header.setObjectName("QP_Header")
        layout.addWidget(header)

        # Item list
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("QP_List")
        self.list_widget.setFrameShape(QListWidget.Shape.NoFrame)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemActivated.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # Hint footer
        hint = QLabel(t("quick_paste_hint"))
        hint.setObjectName("QP_Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _stylesheet(self) -> str:
        return f"""
            QuickPastePopup {{
                background: {DARK_BG};
                border: 1px solid {BORDER_DEFAULT};
                border-radius: 10px;
            }}
            #QP_Header {{
                color: {ACCENT};
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
                text-transform: uppercase;
                padding-bottom: 2px;
            }}
            #QP_List {{
                background: transparent;
                color: {TEXT_PRIMARY};
                font-size: 12px;
            }}
            QListWidget::item {{
                padding: 5px 8px;
                border-radius: 4px;
            }}
            QListWidget::item:selected, QListWidget::item:hover {{
                background: rgba(79,124,255,0.18);
            }}
            #QP_Hint {{
                color: {TEXT_SECONDARY};
                font-size: 10px;
                padding-top: 2px;
            }}
        """

    # ── Public API ─────────────────────────────────────────────────────────
    def show_at_cursor(self, items: list[ClipboardItem]):
        """Populate with *items* (up to QUICK_PASTE_MAX_ITEMS) and show at cursor."""
        self._items = items[:QUICK_PASTE_MAX_ITEMS]
        self._populate()

        # Size the popup
        self.setFixedWidth(340)
        item_height = 30
        header_height = 60
        total_h = min(len(self._items) * item_height + header_height, 380)
        self.setFixedHeight(total_h)

        # Position near cursor, keeping on-screen
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos)
        if screen:
            geom = screen.geometry()
            x = min(pos.x(), geom.right() - self.width() - 10)
            y = min(pos.y(), geom.bottom() - self.height() - 10)
            self.move(x, y)
        else:
            self.move(pos)

        self.show()
        self.raise_()
        self.activateWindow()
        self.list_widget.setFocus()
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def _populate(self):
        self.list_widget.clear()
        for i, item in enumerate(self._items):
            num = str(i + 1) if i < 9 else "•"
            if item.content_type == TYPE_IMAGE:
                text = f"{num}  [Image]"
            else:
                preview = (item.text_content or item.preview or "")[:60]
                preview = preview.replace('\n', ' ↵ ')
                text = f"{num}  {preview}"
            list_item = QListWidgetItem(text)
            list_item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_widget.addItem(list_item)

    # ── Events ─────────────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.hide()
            return
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(self._items):
                self._emit_and_close(self._items[idx])
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            row = self.list_widget.currentRow()
            if 0 <= row < len(self._items):
                self._emit_and_close(self._items[row])
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent):
        super().focusOutEvent(event)
        # Close if neither the popup nor its list has focus
        QTimer.singleShot(100, self._check_focus)

    def _check_focus(self):
        if not self.isActiveWindow():
            self.hide()

    def _on_item_clicked(self, list_item: QListWidgetItem):
        idx = list_item.data(Qt.ItemDataRole.UserRole)
        if idx is not None and 0 <= idx < len(self._items):
            self._emit_and_close(self._items[idx])

    def _emit_and_close(self, item: ClipboardItem):
        self.hide()
        self.paste_requested.emit(item)
