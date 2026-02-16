"""Settings dialog for CyberClip."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QGroupBox, QFormLayout,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from cyberclip.storage.models import AppSettings
from cyberclip.utils.constants import DEFAULT_HOTKEYS, FONT_FAMILY, FONT_FAMILY_FALLBACK, ACCENT


class HotkeyRecorderEdit(QLineEdit):
    """A line edit that records key combinations when focused."""
    hotkey_recorded = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("Nhấn để ghi phím tắt…")
        self._apply_style(False)
        self._recording = False

    def _apply_style(self, active: bool):
        border = f"2px solid {ACCENT}" if active else "1px solid rgba(255,255,255,0.1)"
        color = ACCENT if active else "#B0B0B8"
        self.setStyleSheet(
            f"background: #2C2C2E; border: {border}; "
            f"border-radius: 6px; padding: 6px 10px; color: {color}; "
            "font-size: 12px; font-weight: bold;"
        )

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._recording = True
        self._apply_style(True)
        self.setPlaceholderText("Nhấn tổ hợp phím…")

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._recording = False
        self._apply_style(False)
        self.setPlaceholderText("Nhấn để ghi phím tắt…")

    def keyPressEvent(self, event):
        if not self._recording:
            return
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("Ctrl")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("Shift")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("Alt")

        key_text = QKeySequence(key).toString()
        if key_text:
            parts.append(key_text)

        combo = "+".join(parts)
        if combo:
            self.setText(combo)
            self.hotkey_recorded.emit(combo)
            self.clearFocus()


class SettingsDialog(QDialog):
    settings_changed = pyqtSignal(AppSettings)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("⚙  Cài đặt CyberClip")
        self.setMinimumSize(500, 500)
        self.setModal(True)
        self._hotkey_edits = {}
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title
        title = QLabel("⚙  CÀI ĐẶT")
        title.setStyleSheet(
            f"font-family: '{FONT_FAMILY}', '{FONT_FAMILY_FALLBACK}'; "
            f"font-size: 16px; font-weight: bold; color: {ACCENT}; "
            "letter-spacing: 3px; padding: 4px 0;"
        )
        layout.addWidget(title)

        # Tab widget
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px; }}
            QTabBar::tab {{ background: transparent; padding: 8px 16px; color: #888899;
                           border-bottom: 2px solid transparent; margin-right: 4px; }}
            QTabBar::tab:selected {{ color: {ACCENT}; border-bottom-color: {ACCENT}; }}
            QTabBar::tab:hover {{ color: #E0E0E0; }}
        """)

        # ── General tab ──
        general_tab = QWidget()
        gen_layout = QFormLayout(general_tab)
        gen_layout.setSpacing(12)
        gen_layout.setContentsMargins(12, 12, 12, 12)

        self.picking_combo = QComboBox()
        self.picking_combo.addItems(["FIFO (Vào trước, Ra trước)", "LIFO (Vào sau, Ra trước)"])
        gen_layout.addRow("Kiểu chọn:", self.picking_combo)

        self.strip_check = QCheckBox("Xóa định dạng khi dán")
        gen_layout.addRow(self.strip_check)

        self.auto_enter_check = QCheckBox("Tự nhấn Enter sau dán")
        gen_layout.addRow(self.auto_enter_check)

        self.auto_tab_check = QCheckBox("Tự nhấn Tab sau dán")
        gen_layout.addRow(self.auto_tab_check)

        self.super_paste_check = QCheckBox("Thay thế Ctrl+V (Dán nâng cao)")
        gen_layout.addRow(self.super_paste_check)

        tabs.addTab(general_tab, "Chung")

        # ── Hotkeys tab ──
        hotkey_tab = QWidget()
        hk_layout = QVBoxLayout(hotkey_tab)
        hk_layout.setSpacing(10)
        hk_layout.setContentsMargins(12, 12, 12, 12)

        hk_info = QLabel("Phím tắt toàn cục — nhấn vào ô rồi bấm tổ hợp phím mong muốn")
        hk_info.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold;")
        hk_info.setWordWrap(True)
        hk_layout.addWidget(hk_info)

        hotkey_actions = {
            "sequential_paste": "Dán tuần tự (dán & chuyển tiếp)",
            "paste_all": "Dán hàng loạt (dán tất cả)",
            "toggle_window": "Hiện / Ẩn CyberClip",
            "skip_item": "Bỏ qua mục tiếp theo",
            "ghost_mode": "Bật/Tắt chế độ ẩn",
        }

        for action, label_text in hotkey_actions.items():
            row = QHBoxLayout()
            label = QLabel(label_text)
            label.setFixedWidth(220)
            label.setStyleSheet("color: #888899; font-size: 11px;")
            row.addWidget(label)

            recorder = HotkeyRecorderEdit()
            recorder.setFixedWidth(180)
            self._hotkey_edits[action] = recorder
            row.addWidget(recorder)
            row.addStretch()
            hk_layout.addLayout(row)

        hk_layout.addSpacing(8)

        ref_label = QLabel("Phím tắt trong ứng dụng (không thể thay đổi)")
        ref_label.setStyleSheet("color: #555566; font-size: 10px; margin-top: 8px;")
        hk_layout.addWidget(ref_label)

        in_app_shortcuts = [
            ("Enter", "Sao chép mục đã chọn"),
            ("↑ / ↓", "Di chuyển giữa các mục"),
            ("Delete", "Xóa mục đã chọn"),
            ("Ctrl+P", "Ghim / Bỏ ghim"),
            ("Ctrl+F", "Tìm kiếm"),
            ("Escape", "Ẩn / Dừng dán hàng loạt"),
        ]
        for key, desc in in_app_shortcuts:
            row = QHBoxLayout()
            key_lbl = QLabel(key)
            key_lbl.setFixedWidth(80)
            key_lbl.setStyleSheet(
                f"background: rgba(79,124,255,0.05); border: 1px solid rgba(79,124,255,0.15); "
                "border-radius: 3px; padding: 2px 6px; color: #555566; font-size: 10px;"
            )
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #555566; font-size: 10px;")
            row.addWidget(key_lbl)
            row.addWidget(desc_lbl, 1)
            hk_layout.addLayout(row)

        reset_hk_btn = QPushButton("Đặt lại phím tắt mặc định")
        reset_hk_btn.clicked.connect(self._reset_hotkeys)
        hk_layout.addSpacing(6)
        hk_layout.addWidget(reset_hk_btn)

        hk_layout.addStretch()

        tabs.addTab(hotkey_tab, "Phím tắt")

        layout.addWidget(tabs)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾  Lưu")
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_values(self):
        s = self.settings
        self.picking_combo.setCurrentIndex(0 if s.picking_style == "FIFO" else 1)
        self.strip_check.setChecked(s.strip_formatting)
        self.auto_enter_check.setChecked(s.auto_enter)
        self.auto_tab_check.setChecked(s.auto_tab)
        self.super_paste_check.setChecked(s.super_paste_enabled)

        # Load hotkeys
        hotkeys = dict(DEFAULT_HOTKEYS)
        if s.hotkeys:
            hotkeys.update(s.hotkeys)
        for action, edit in self._hotkey_edits.items():
            if action in hotkeys:
                edit.setText(hotkeys[action])

    def _save(self):
        s = self.settings
        s.picking_style = "FIFO" if self.picking_combo.currentIndex() == 0 else "LIFO"
        s.strip_formatting = self.strip_check.isChecked()
        s.auto_enter = self.auto_enter_check.isChecked()
        s.auto_tab = self.auto_tab_check.isChecked()
        s.super_paste_enabled = self.super_paste_check.isChecked()

        # Save hotkeys
        hotkeys = {}
        for action, edit in self._hotkey_edits.items():
            text = edit.text().strip()
            if text:
                hotkeys[action] = text
        s.hotkeys = hotkeys

        self.settings_changed.emit(s)
        self.accept()

    def _reset_hotkeys(self):
        for action, edit in self._hotkey_edits.items():
            if action in DEFAULT_HOTKEYS:
                edit.setText(DEFAULT_HOTKEYS[action])
