"""Individual clipboard item card widget with animations."""
import os
import json
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QGraphicsOpacityEffect, QApplication, QMenu, QSizePolicy,
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve,
    QSize, QPoint, QParallelAnimationGroup, QTimer, QRect,
    QMimeData,
)
from PyQt6.QtGui import QPixmap, QColor, QPainter, QCursor, QIcon, QDrag

from cyberclip.storage.models import ClipboardItem
from cyberclip.utils.constants import (
    TYPE_TEXT, TYPE_IMAGE, TYPE_FILE, TYPE_URL, TYPE_COLOR,
    NEON_CYAN, NEON_PURPLE, NEON_PINK, TEXT_DIM,
)
from cyberclip.utils.i18n import t


class ClipItemWidget(QWidget):
    clicked = pyqtSignal(ClipboardItem)
    paste_requested = pyqtSignal(ClipboardItem)
    delete_requested = pyqtSignal(ClipboardItem)
    pin_toggled = pyqtSignal(ClipboardItem)
    ocr_requested = pyqtSignal(ClipboardItem)
    open_file_requested = pyqtSignal(str)
    start_from_here = pyqtSignal(ClipboardItem)
    view_image_requested = pyqtSignal(ClipboardItem)

    # Nerd Font icons
    ICON_TEXT = "\uf15c"    # 
    ICON_IMAGE = "\uf03e"   # 
    ICON_FILE = "\uf07b"    # 
    ICON_URL = "\uf0c1"     # 
    ICON_COLOR = "\uf53f"   # 
    ICON_PIN = "\uf08d"     # 
    ICON_UNPIN = "\uf08d"
    ICON_PASTE = "\uf0ea"   # 
    ICON_DELETE = "\uf2ed"  # 
    ICON_OCR = "\uf065"     # 
    ICON_COPY = "\uf0c5"    # 
    ICON_OPEN = "\uf35d"    # 
    ICON_VIEW = "\uf06e"    # eye icon
    ICON_COLLAPSE = "\uf078"  # chevron down
    ICON_EXPAND = "\uf077"    # chevron up

    TYPE_ICONS = {
        TYPE_TEXT: ICON_TEXT,
        TYPE_IMAGE: ICON_IMAGE,
        TYPE_FILE: ICON_FILE,
        TYPE_URL: ICON_URL,
        TYPE_COLOR: ICON_COLOR,
    }

    def __init__(self, item: ClipboardItem, parent=None):
        super().__init__(parent)
        self.item = item
        self._selected = False
        self._collapsed = False
        self.setObjectName("ClipCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("pinned", str(item.pinned).lower())
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setMinimumHeight(40)
        self._content_widgets = []  # track content area widgets for collapse
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 8, 8)
        main_layout.setSpacing(10)

        # Magazine position badge (hidden by default)
        self.queue_badge = QLabel("▶")
        self.queue_badge.setObjectName("QueueBadge")
        self.queue_badge.setFixedWidth(16)
        self.queue_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.queue_badge.setVisible(False)
        main_layout.addWidget(self.queue_badge)

        # Type icon
        icon_text = self.TYPE_ICONS.get(self.item.content_type, self.ICON_TEXT)
        self.type_icon = QLabel(icon_text)
        self.type_icon.setObjectName("ClipTypeIcon")
        self.type_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.type_icon.setFixedSize(32, 32)
        main_layout.addWidget(self.type_icon)

        # Content area — takes remaining space, shrinks as needed
        content_widget = QWidget()
        content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Main content
        if self.item.content_type == TYPE_IMAGE:
            self._setup_image_content(content_layout)
        elif self.item.content_type == TYPE_COLOR:
            self._setup_color_content(content_layout)
        else:
            self._setup_text_content(content_layout)

        # Metadata line
        meta_parts = []
        try:
            dt = datetime.fromisoformat(self.item.created_at)
            meta_parts.append(dt.strftime("%H:%M"))
        except Exception:
            pass
        if self.item.source_app:
            app_name = self.item.source_app.replace(".exe", "")
            meta_parts.append(app_name)
        if self.item.content_type == TYPE_TEXT:
            char_count = len(self.item.text_content)
            word_count = len(self.item.text_content.split())
            line_count = self.item.text_content.count('\n') + 1
            if char_count > 100:
                meta_parts.append(f"{word_count}w · {line_count}L · {char_count}ch")
            else:
                meta_parts.append(f"{word_count} từ")

        if meta_parts:
            self.meta_label = QLabel("  ·  ".join(meta_parts))
            self.meta_label.setObjectName("ClipMeta")
            content_layout.addWidget(self.meta_label)

        main_layout.addWidget(content_widget, 1)

        # Action buttons (right side)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(2)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        # Collapse/Expand button (default: compact view, click to expand)
        self.collapse_btn = QPushButton(self.ICON_EXPAND)
        self.collapse_btn.setObjectName("ClipAction")
        self.collapse_btn.setFixedSize(28, 28)
        self.collapse_btn.setToolTip("Mở rộng")
        self.collapse_btn.clicked.connect(self._toggle_collapse)
        actions_layout.addWidget(self.collapse_btn)

        # Pin button
        self.pin_btn = QPushButton(self.ICON_PIN)
        self.pin_btn.setObjectName("PinButton")
        self.pin_btn.setProperty("pinned", str(self.item.pinned).lower())
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setToolTip(t("unpin") if self.item.pinned else t("pin"))
        self.pin_btn.clicked.connect(lambda: self.pin_toggled.emit(self.item))
        actions_layout.addWidget(self.pin_btn)

        # Paste button
        paste_btn = QPushButton(self.ICON_PASTE)
        paste_btn.setObjectName("ClipAction")
        paste_btn.setFixedSize(28, 28)
        paste_btn.setToolTip(t("paste"))
        paste_btn.clicked.connect(lambda: self.paste_requested.emit(self.item))
        actions_layout.addWidget(paste_btn)

        # Type-specific buttons
        if self.item.content_type == TYPE_IMAGE:
            # View image button
            view_btn = QPushButton(self.ICON_VIEW)
            view_btn.setObjectName("ClipAction")
            view_btn.setFixedSize(28, 28)
            view_btn.setToolTip(t("view_image"))
            view_btn.clicked.connect(lambda: self.view_image_requested.emit(self.item))
            actions_layout.addWidget(view_btn)

            ocr_btn = QPushButton(self.ICON_OCR)
            ocr_btn.setObjectName("ClipAction")
            ocr_btn.setFixedSize(28, 28)
            ocr_btn.setToolTip(t("ocr_scan"))
            ocr_btn.clicked.connect(lambda: self.ocr_requested.emit(self.item))
            actions_layout.addWidget(ocr_btn)

        if self.item.content_type == TYPE_FILE:
            open_btn = QPushButton(self.ICON_OPEN)
            open_btn.setObjectName("ClipAction")
            open_btn.setFixedSize(28, 28)
            open_btn.setToolTip(t("open_explorer"))
            open_btn.clicked.connect(lambda: self.open_file_requested.emit(self.item.text_content))
            actions_layout.addWidget(open_btn)

        # Copy button for text/url
        if self.item.content_type in (TYPE_TEXT, TYPE_URL):
            copy_btn = QPushButton(self.ICON_COPY)
            copy_btn.setObjectName("ClipAction")
            copy_btn.setFixedSize(28, 28)
            copy_btn.setToolTip(t("copy"))
            copy_btn.clicked.connect(lambda: self._copy_to_clipboard())
            actions_layout.addWidget(copy_btn)

        # Delete button
        del_btn = QPushButton(self.ICON_DELETE)
        del_btn.setObjectName("ClipAction")
        del_btn.setFixedSize(28, 28)
        del_btn.setToolTip("Xóa")
        del_btn.clicked.connect(lambda: self.delete_requested.emit(self.item))
        actions_layout.addWidget(del_btn)

        main_layout.addLayout(actions_layout)

    def _setup_text_content(self, layout):
        text = self.item.text_content or self.item.preview
        lines = text.split('\n')
        # Collapsed preview (compact — always visible)
        first_line = lines[0][:80]
        if len(lines[0]) > 80:
            first_line += "…"
        extra = ""
        if len(lines) > 1:
            extra = f"  (+{len(lines)-1} dòng)"
        display = first_line + extra
        self.content_label = QLabel(display)
        self.content_label.setObjectName("ClipContent")
        self.content_label.setWordWrap(False)
        self.content_label.setTextFormat(Qt.TextFormat.PlainText)
        self.content_label.setMaximumHeight(20)
        self.content_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.content_label)

        # Expanded full content (hidden by default)
        self.full_content_label = QLabel(text[:2000])  # limit to 2000 chars
        self.full_content_label.setObjectName("ClipContent")
        self.full_content_label.setWordWrap(True)
        self.full_content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.full_content_label.setVisible(False)
        layout.addWidget(self.full_content_label)
        self._content_widgets.append(self.full_content_label)

    def _setup_image_content(self, layout):
        self.thumb_label = QLabel()
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.thumb_label.setStyleSheet(
            "border-radius: 6px; border: 1px solid rgba(255,255,255,0.08); padding: 0px;"
        )

        pix = None
        if os.path.exists(self.item.image_path):
            pix = QPixmap(self.item.image_path)
            if not pix.isNull():
                # Cap height at 80px, scale to fit
                if pix.height() > 80:
                    scaled = pix.scaledToHeight(
                        80, Qt.TransformationMode.SmoothTransformation
                    )
                else:
                    scaled = pix
                self.thumb_label.setPixmap(scaled)
                self.thumb_label.setFixedSize(scaled.width(), scaled.height())
        layout.addWidget(self.thumb_label, 0, Qt.AlignmentFlag.AlignLeft)
        self._content_widgets.append(self.thumb_label)

        # Image info line
        info_parts = []
        if pix and not pix.isNull():
            info_parts.append(f"{pix.width()}×{pix.height()}")
        if os.path.exists(self.item.image_path):
            size_bytes = os.path.getsize(self.item.image_path)
            if size_bytes > 1024 * 1024:
                info_parts.append(f"{size_bytes / (1024*1024):.1f} MB")
            else:
                info_parts.append(f"{size_bytes / 1024:.1f} KB")

        if info_parts:
            info_label = QLabel("  ·  ".join(info_parts))
            info_label.setObjectName("ClipMeta")
            layout.addWidget(info_label)

    def _setup_color_content(self, layout):
        color_layout = QHBoxLayout()
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(8)

        self.swatch = QLabel()
        self.swatch.setObjectName("ColorSwatch")
        self.swatch.setFixedSize(32, 20)
        color_str = self.item.text_content
        self.swatch.setStyleSheet(
            f"background-color: {color_str}; border-radius: 5px; "
            f"border: 1px solid rgba(255,255,255,0.15);"
        )
        color_layout.addWidget(self.swatch)

        color_label = QLabel(color_str)
        color_label.setObjectName("ClipContent")
        color_layout.addWidget(color_label, 1)

        layout.addLayout(color_layout)

    def _toggle_collapse(self):
        """Toggle between compact preview and expanded full content."""
        self._collapsed = not self._collapsed
        if self._collapsed:
            # Expanded state: show full content, hide compact preview
            if hasattr(self, 'content_label'):
                self.content_label.setVisible(False)
            for w in self._content_widgets:
                w.setVisible(True)
            self.collapse_btn.setText(self.ICON_COLLAPSE)
            self.collapse_btn.setToolTip("Thu gọn")
        else:
            # Collapsed/compact state: show compact preview, hide full content
            if hasattr(self, 'content_label'):
                self.content_label.setVisible(True)
            for w in self._content_widgets:
                w.setVisible(False)
            self.collapse_btn.setText(self.ICON_EXPAND)
            self.collapse_btn.setToolTip("Mở rộng")

    def _setup_animation(self):
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def animate_in(self, delay_ms: int = 0):
        self._opacity_effect.setOpacity(0.0)
        self.setMaximumHeight(0)

        group = QParallelAnimationGroup(self)

        opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        opacity_anim.setDuration(350)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.OutQuart)
        group.addAnimation(opacity_anim)

        height_anim = QPropertyAnimation(self, b"maximumHeight")
        height_anim.setDuration(400)
        height_anim.setStartValue(0)
        height_anim.setEndValue(160)
        height_anim.setEasingCurve(QEasingCurve.Type.OutQuart)
        group.addAnimation(height_anim)

        QTimer.singleShot(delay_ms, group.start)
        self._anim_group = group

    def animate_out(self, callback=None):
        group = QParallelAnimationGroup(self)

        opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        opacity_anim.setDuration(250)
        opacity_anim.setStartValue(1.0)
        opacity_anim.setEndValue(0.0)
        opacity_anim.setEasingCurve(QEasingCurve.Type.InQuart)
        group.addAnimation(opacity_anim)

        height_anim = QPropertyAnimation(self, b"maximumHeight")
        height_anim.setDuration(300)
        height_anim.setStartValue(self.height())
        height_anim.setEndValue(0)
        height_anim.setEasingCurve(QEasingCurve.Type.InQuart)
        group.addAnimation(height_anim)

        if callback:
            group.finished.connect(callback)
        group.start()
        self._anim_group = group

    def set_selected(self, selected: bool):
        self._selected = selected
        self.setProperty("selected", str(selected).lower())
        self.style().unpolish(self)
        self.style().polish(self)

    def set_magazine_active(self, active: bool):
        """Highlight this item as the current magazine queue item."""
        self.queue_badge.setVisible(active)
        self.setProperty("magazine_active", str(active).lower())
        self.style().unpolish(self)
        self.style().polish(self)

    def update_pin_state(self, pinned: bool):
        self.item.pinned = pinned
        self.pin_btn.setProperty("pinned", str(pinned).lower())
        self.setProperty("pinned", str(pinned).lower())
        self.pin_btn.setToolTip("Bỏ ghim" if pinned else "Ghim")
        self.pin_btn.style().unpolish(self.pin_btn)
        self.pin_btn.style().polish(self.pin_btn)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self.clicked.emit(self.item)
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return super().mouseMoveEvent(event)
        if not hasattr(self, '_drag_start_pos') or self._drag_start_pos is None:
            return super().mouseMoveEvent(event)
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            return super().mouseMoveEvent(event)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-cyberclip-item-id", str(self.item.id).encode())
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.item.content_type == TYPE_IMAGE:
                self.view_image_requested.emit(self.item)
            else:
                self.paste_requested.emit(self.item)
        super().mouseDoubleClickEvent(event)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        # Force opaque dark background (QSS alone may not override popup transparency)
        menu.setStyleSheet(
            "QMenu { background-color: #1C1C1E; border: 1px solid rgba(255,255,255,0.12); "
            "border-radius: 8px; padding: 4px 0px; }"
            "QMenu::item { background-color: transparent; padding: 8px 32px 8px 14px; "
            "border-radius: 4px; margin: 2px 6px; color: #F5F5F7; font-size: 12px; }"
            "QMenu::item:selected { background-color: rgba(255,255,255,0.10); }"
            "QMenu::separator { height: 1px; background-color: rgba(255,255,255,0.08); "
            "margin: 4px 12px; }"
        )
        menu.addAction(t("ctx_start_here"), lambda: self.start_from_here.emit(self.item))
        menu.addSeparator()
        menu.addAction(t("ctx_copy"), lambda: self._copy_to_clipboard())
        menu.addAction(t("ctx_pin"), lambda: self.pin_toggled.emit(self.item))

        if self.item.content_type == TYPE_IMAGE:
            menu.addSeparator()
            menu.addAction(t("ctx_view_image"), lambda: self.view_image_requested.emit(self.item))
            menu.addAction(t("ctx_ocr"), lambda: self.ocr_requested.emit(self.item))

        if self.item.content_type == TYPE_FILE:
            menu.addSeparator()
            menu.addAction(t("ctx_open_explorer"),
                          lambda: self.open_file_requested.emit(self.item.text_content))

        menu.addSeparator()
        menu.addAction(t("ctx_delete"), lambda: self.delete_requested.emit(self.item))
        menu.exec(pos)

    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        if self.item.content_type == TYPE_IMAGE and self.item.image_path:
            pix = QPixmap(self.item.image_path)
            if not pix.isNull():
                clipboard.setPixmap(pix)
                return
        clipboard.setText(self.item.text_content or self.item.preview or "")
