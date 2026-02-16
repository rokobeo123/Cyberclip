"""Choice menu popup - shows when holding paste key."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QPainter, QColor


class ChoiceMenu(QWidget):
    original_selected = pyqtSignal()
    next_selected = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup |
                         Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName("ChoiceMenu")
        self.setFixedWidth(220)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self.original_btn = QPushButton("\uf0c5  Paste Original")
        self.original_btn.setObjectName("ChoiceItem")
        self.original_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.original_btn.clicked.connect(self._on_original)
        layout.addWidget(self.original_btn)

        self.next_btn = QPushButton("\uf061  Paste Next in Queue")
        self.next_btn.setObjectName("ChoiceItem")
        self.next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.next_btn.clicked.connect(self._on_next)
        layout.addWidget(self.next_btn)

    def show_at(self, pos: QPoint):
        self.move(pos)
        self.show()
        # Animate in
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(150)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def _on_original(self):
        self.original_selected.emit()
        self.close()

    def _on_next(self):
        self.next_selected.emit()
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(18, 18, 26, 240))
        painter.setPen(QColor(0, 240, 255, 50))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.end()
