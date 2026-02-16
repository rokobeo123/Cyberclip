"""Tab bar widget for app-specific clipboard categories."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve


class TabBar(QWidget):
    tab_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TabBar")
        self._tabs = ["General"]
        self._active = "General"
        self._buttons = {}
        self._setup_ui()

    def _setup_ui(self):
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(36)
        self._scroll.setStyleSheet("background: transparent; border: none;")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(4, 2, 4, 2)
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._container)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll)

        self._rebuild()

    def set_tabs(self, tabs: list):
        self._tabs = list(tabs)
        if "General" not in self._tabs:
            self._tabs.insert(0, "General")
        if self._active not in self._tabs:
            self._active = self._tabs[0]
        self._rebuild()

    def add_tab(self, name: str):
        if name not in self._tabs:
            self._tabs.append(name)
            self._rebuild()

    def set_active(self, name: str):
        if name in self._tabs and name != self._active:
            self._active = name
            self._update_styles()
            self.tab_changed.emit(name)

    def get_active(self) -> str:
        return self._active

    def _rebuild(self):
        # Clear existing
        for btn in self._buttons.values():
            btn.deleteLater()
        self._buttons.clear()

        while self._layout.count():
            self._layout.takeAt(0)

        for tab_name in self._tabs:
            btn = QPushButton(tab_name)
            btn.setObjectName("TabButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, n=tab_name: self.set_active(n))
            self._buttons[tab_name] = btn
            self._layout.addWidget(btn)

        self._layout.addStretch()
        self._update_styles()

    def _update_styles(self):
        for name, btn in self._buttons.items():
            is_active = (name == self._active)
            btn.setProperty("active", str(is_active).lower())
            btn.style().unpolish(btn)
            btn.style().polish(btn)
