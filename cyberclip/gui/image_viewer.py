"""Image viewer dialog with zoom and pan."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QApplication,
)
from PyQt6.QtCore import Qt, QPoint, QSize
from PyQt6.QtGui import QPixmap, QPainter, QWheelEvent, QMouseEvent, QCursor


class ZoomableImageLabel(QLabel):
    """A label that supports zoom via scroll wheel and pan via drag."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._original = pixmap
        self._zoom = 1.0
        self._min_zoom = 0.1
        self._max_zoom = 10.0
        self._pan_start = QPoint()
        self._dragging = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self._update_display()

    @property
    def zoom(self):
        return self._zoom

    def set_zoom(self, z: float):
        self._zoom = max(self._min_zoom, min(self._max_zoom, z))
        self._update_display()

    def _update_display(self):
        if self._original.isNull():
            return
        w = int(self._original.width() * self._zoom)
        h = int(self._original.height() * self._zoom)
        scaled = self._original.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
        self.setFixedSize(scaled.size())

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self.set_zoom(self._zoom * factor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._pan_start = event.globalPosition().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseReleaseEvent(self, event: QMouseEvent):
        self._dragging = False
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._dragging:
            delta = event.globalPosition().toPoint() - self._pan_start
            self._pan_start = event.globalPosition().toPoint()
            scroll = self.parent()
            if scroll and hasattr(scroll, 'parent'):
                sa = scroll.parent()
                if isinstance(sa, QScrollArea):
                    h = sa.horizontalScrollBar()
                    v = sa.verticalScrollBar()
                    h.setValue(h.value() - delta.x())
                    v.setValue(v.value() - delta.y())


class ImageViewerDialog(QDialog):
    """Full image viewer with zoom in/out and fit-to-window."""

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🖼  Xem ảnh")
        self.setMinimumSize(600, 450)
        self.resize(800, 600)
        self.setStyleSheet(
            "QDialog { background: #1C1C1E; }"
            "QLabel { color: #E0E0E8; }"
            "QPushButton { background: #2C2C2E; border: 1px solid rgba(255,255,255,0.1); "
            "border-radius: 6px; padding: 6px 14px; color: #E0E0E8; font-size: 12px; }"
            "QPushButton:hover { background: #3A3A3C; }"
            "QScrollArea { border: none; background: transparent; }"
        )
        self._setup_ui(image_path)

    def _setup_ui(self, image_path: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setToolTip("Phóng to")
        zoom_in_btn.setFixedWidth(50)
        zoom_in_btn.clicked.connect(lambda: self._zoom(1.25))
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("🔍−")
        zoom_out_btn.setToolTip("Thu nhỏ")
        zoom_out_btn.setFixedWidth(50)
        zoom_out_btn.clicked.connect(lambda: self._zoom(0.8))
        toolbar.addWidget(zoom_out_btn)

        fit_btn = QPushButton("Vừa cửa sổ")
        fit_btn.clicked.connect(self._fit_to_window)
        toolbar.addWidget(fit_btn)

        actual_btn = QPushButton("100%")
        actual_btn.clicked.connect(self._actual_size)
        toolbar.addWidget(actual_btn)

        toolbar.addStretch()

        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("color: #888899; font-size: 11px;")
        toolbar.addWidget(self.zoom_label)

        layout.addLayout(toolbar)

        # Scroll area with zoomable image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            err = QLabel("Không thể tải ảnh")
            err.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(err)
            return

        self.image_label = ZoomableImageLabel(pixmap)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        # Info bar
        info = QLabel(f"{pixmap.width()} × {pixmap.height()} px")
        info.setStyleSheet("color: #555566; font-size: 10px;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        # Start fitted
        self._fit_to_window()

    def _zoom(self, factor: float):
        if hasattr(self, 'image_label'):
            self.image_label.set_zoom(self.image_label.zoom * factor)
            self.zoom_label.setText(f"{int(self.image_label.zoom * 100)}%")

    def _fit_to_window(self):
        if not hasattr(self, 'image_label'):
            return
        sa_size = self.scroll_area.size()
        orig = self.image_label._original
        if orig.isNull():
            return
        zw = (sa_size.width() - 20) / orig.width()
        zh = (sa_size.height() - 20) / orig.height()
        self.image_label.set_zoom(min(zw, zh))
        self.zoom_label.setText(f"{int(self.image_label.zoom * 100)}%")

    def _actual_size(self):
        if hasattr(self, 'image_label'):
            self.image_label.set_zoom(1.0)
            self.zoom_label.setText("100%")

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, self._fit_to_window)
