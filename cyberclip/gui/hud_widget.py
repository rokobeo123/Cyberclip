"""Floating toast notification widget - shows briefly then auto-hides."""
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer
from PyQt6.QtGui import QPainter, QColor


class HUDWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool |
                         Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("HUD")
        self.setFixedSize(260, 44)
        self._setup_ui()
        self._position_bottom_right()
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._fade_out)
        # Start hidden
        self.setWindowOpacity(0.0)
        self.hide()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        self.icon_label = QLabel("\uf0ea")  # paste icon
        self.icon_label.setObjectName("HUDLabel")
        self.icon_label.setFixedWidth(20)
        layout.addWidget(self.icon_label)

        self.info_label = QLabel("")
        self.info_label.setObjectName("HUDLabel")
        layout.addWidget(self.info_label, 1)

    def update_info(self, current: int, total: int, preview: str = ""):
        if total == 0:
            return  # don't show for empty queue
        if current >= total:
            self._show_toast("✓ Hàng đợi đã hết")
        else:
            text = f"▶ {current+1}/{total}"
            if preview:
                short = preview[:25] + "…" if len(preview) > 25 else preview
                text += f"  {short}"
            self._show_toast(text)

    def set_ghost_mode(self, active: bool):
        if active:
            self.icon_label.setText("\uf21b")  # ghost
            self._show_toast("Chế độ ẩn: BẬT", duration=2000)
        else:
            self.icon_label.setText("\uf0ea")
            self._show_toast("Chế độ ẩn: TẮT", duration=2000)

    def notify(self, message: str, duration: int = 2500):
        """Show a generic toast notification."""
        self._show_toast(message, duration)

    def _show_toast(self, text: str, duration: int = 2500):
        """Show the toast, then auto-hide after duration ms."""
        self.info_label.setText(text)
        self._auto_hide_timer.stop()

        self.show()
        self._position_bottom_right()

        # Fade in
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(200)
        anim.setStartValue(self.windowOpacity())
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._fade_in_anim = anim

        self._auto_hide_timer.start(duration)

    def _fade_out(self):
        """Fade out and hide."""
        anim = QPropertyAnimation(self, b"windowOpacity")
        anim.setDuration(400)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.finished.connect(self.hide)
        anim.start()
        self._fade_out_anim = anim

    def flash(self):
        """Show briefly with a flash."""
        pass  # Now handled by _show_toast

    def _position_bottom_right(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - 20
            y = geo.bottom() - self.height() - 20
            self.move(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(28, 28, 30, 230))
        painter.setPen(QColor(255, 255, 255, 18))
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        painter.end()
