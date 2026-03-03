"""Internationalization strings for CyberClip."""

_STRINGS = {
    "vi": {
        # Title / Window
        "app_title": "CyberClip",
        "settings_title": "⚙  Cài đặt CyberClip",
        "settings_header": "⚙  CÀI ĐẶT",

        # Tabs
        "tab_general": "Chung",
        "tab_hotkeys": "Phím tắt",

        # General settings
        "picking_style": "Kiểu chọn:",
        "fifo_label": "FIFO (Vào trước, Ra trước)",
        "lifo_label": "LIFO (Vào sau, Ra trước)",
        "strip_formatting": "Xóa định dạng khi dán",
        "auto_enter": "Tự nhấn Enter sau dán",
        "auto_tab": "Tự nhấn Tab sau dán",
        "super_paste": "Thay thế Ctrl+V (Dán nâng cao)",
        "language": "Ngôn ngữ:",

        # Hotkeys
        "hotkey_info": "Phím tắt toàn cục — nhấn vào ô rồi bấm tổ hợp phím mong muốn",
        "hotkey_record_placeholder": "Nhấn để ghi phím tắt…",
        "hotkey_record_active": "Nhấn tổ hợp phím…",
        "sequential_paste": "Dán tuần tự (dán & chuyển tiếp)",
        "paste_all": "Dán hàng loạt (dán tất cả)",
        "toggle_window": "Hiện / Ẩn CyberClip",
        "skip_item": "Bỏ qua mục tiếp theo",
        "ghost_mode_hotkey": "Bật/Tắt chế độ ẩn",
        "in_app_shortcuts_label": "Phím tắt trong ứng dụng (không thể thay đổi)",
        "shortcut_copy": "Sao chép mục đã chọn",
        "shortcut_navigate": "Di chuyển giữa các mục",
        "shortcut_delete": "Xóa mục đã chọn",
        "shortcut_pin": "Ghim / Bỏ ghim",
        "shortcut_search": "Tìm kiếm",
        "shortcut_escape": "Ẩn / Dừng dán hàng loạt",
        "reset_hotkeys": "Đặt lại phím tắt mặc định",

        # Buttons
        "paste_delay": "Độ trễ giữa các lần dán:",
        "paste_delay_tooltip": "Thời gian chờ giữa mỗi lần dán khi dán hàng loạt. Tăng lên nếu bị mất nội dung (ví dụ: Gemini, ChatGPT). Mặc định: 500ms",
        "max_items": "Số mục tối đa mỗi tab:",
        "max_items_tooltip": "Khi vượt quá giới hạn, các mục cũ nhất (không ghim) sẽ tự động bị xóa. Mặc định: 200",
        "paste_all_count": "Số mục mỗi lần (Ctrl+Shift+A):",
        "paste_all_count_tooltip": "Số mục dán mỗi lần nhấn Ctrl+Shift+A. 0 (∞) = dán tất cả còn lại.",

        # Toolbar / Main window
        "search_placeholder": "Tìm kiếm…",
        "reset_queue": "Đặt lại hàng đợi",
        "clear_tab": "Xóa tất cả",
        "pin_filter": "Chỉ ghim",
        "collapse_all": "Thu gọn tất cả",
        "expand_all": "Mở rộng tất cả",
        "ghost_mode": "Chế độ ẩn",
        "settings": "Cài đặt",
        "items_count": "{count} mục",
        "ready": "Sẵn sàng",

        # Paste messages
        "copied_ctrlv": "✓ Đã sao chép — Ctrl+V để dán",
        "pasted_next": "✓ Đã dán — tiếp: {preview}",
        "pasted_done": "✓ Đã dán — hết hàng đợi",
        "queue_empty": "⚠ Hàng đợi trống",
        "queue_reset": "▶ Đặt lại hàng đợi ({mode})",
        "skip_next": "⏭ Bỏ qua — tiếp: {preview}",
        "skip_done": "⏭ Bỏ qua — hết hàng đợi",
        "cleared_tab": "Đã xóa: {tab}",
        "ghost_on": "Chế độ ẩn: BẬT",
        "ghost_off": "Chế độ ẩn: TẮT",
        "pin_only": "Chỉ hiện mục đã ghim",
        "show_all": "Hiện tất cả",
        "paste_all_start": "▶ Dán hàng loạt: {count} mục",
        "paste_all_stop": "⏹ Dừng dán hàng loạt",
        "paste_all_stopped": "⏹ Đã dừng dán hàng loạt",
        "paste_all_progress": "⏳ Đang dán {done}/{total} — tiếp: {preview}",
        "paste_all_done": "✓ Đã dán xong {total} mục",
        "paste_busy": "⚠ Đang dán, vui lòng chờ…",
        "paste_timeout": "⚠ Dán bị treo — đã tự khôi phục",
        "words": "{count} từ",

        # Item widget
        "pin": "Ghim",
        "unpin": "Bỏ ghim",
        "paste": "Dán",
        "view_image": "Xem ảnh",
        "ocr_scan": "Quét văn bản (OCR)",
        "open_explorer": "Mở trong Explorer",
        "copy": "Sao chép",
        "delete": "Xóa",
        "expand": "Mở rộng",
        "collapse": "Thu gọn",
        "start_from_here": "Bắt đầu từ đây",
        "lines_more": "(+{count} dòng)",

        # Context menu
        "ctx_start_here": "▶ Bắt đầu từ đây",
        "ctx_paste": "📋 Dán",
        "ctx_pin": "📌 Ghim/Bỏ ghim",
        "ctx_copy": "📑 Sao chép",
        "ctx_view_image": "👁 Xem ảnh",
        "ctx_ocr": "🔍 Quét OCR",
        "ctx_open_explorer": "📂 Mở trong Explorer",
        "ctx_delete": "🗑️ Xóa",

        # Tray
        "tray_show": "Hiện CyberClip",
        "tray_ghost": "Chế độ ẩn",
        "tray_settings": "Cài đặt",
        "tray_quit": "Thoát",

        # Empty state
        "empty_title": "Chưa có gì",
        "empty_subtitle": "Copy nội dung để bắt đầu",

        # OCR
        "ocr_scanning": "Đang quét văn bản (OCR)…",
        "ocr_extracted": "OCR: {count} ký tự được trích xuất",
        "ocr_no_text": "OCR: Không tìm thấy văn bản",

        # Image viewer
        "img_viewer_title": "🖼  Xem ảnh",
        "img_zoom_in": "Phóng to",
        "img_zoom_out": "Thu nhỏ",
        "img_fit_window": "Vừa cửa sổ",
        "img_actual_size": "100%",
        "img_load_error": "Không thể tải ảnh",

        # Choice menu
        "choice_paste_original": "Dán bản gốc",
        "choice_paste_next": "Dán mục tiếp theo",
    },

    "en": {
        "app_title": "CyberClip",
        "settings_title": "⚙  CyberClip Settings",
        "settings_header": "⚙  SETTINGS",

        "tab_general": "General",
        "tab_hotkeys": "Hotkeys",

        "picking_style": "Picking style:",
        "fifo_label": "FIFO (First In, First Out)",
        "lifo_label": "LIFO (Last In, First Out)",
        "strip_formatting": "Strip formatting when pasting",
        "auto_enter": "Auto-press Enter after paste",
        "auto_tab": "Auto-press Tab after paste",
        "super_paste": "Replace Ctrl+V (Advanced paste)",
        "language": "Language:",

        "hotkey_info": "Global hotkeys — click the box and press your desired key combination",
        "hotkey_record_placeholder": "Click to record hotkey…",
        "hotkey_record_active": "Press key combination…",
        "sequential_paste": "Sequential paste (paste & advance)",
        "paste_all": "Paste all (paste entire queue)",
        "toggle_window": "Show / Hide CyberClip",
        "skip_item": "Skip next item",
        "ghost_mode_hotkey": "Toggle ghost mode",
        "in_app_shortcuts_label": "In-app shortcuts (cannot be changed)",
        "shortcut_copy": "Copy selected item",
        "shortcut_navigate": "Navigate between items",
        "shortcut_delete": "Delete selected item",
        "shortcut_pin": "Pin / Unpin",
        "shortcut_search": "Search",
        "shortcut_escape": "Hide / Stop batch paste",
        "reset_hotkeys": "Reset hotkeys to defaults",

        "paste_delay": "Paste delay:",
        "paste_delay_tooltip": "Wait time between each item in paste-all. Increase if items are missed (e.g. Gemini, ChatGPT). Default: 500ms",
        "max_items": "Max items per tab:",
        "max_items_tooltip": "Oldest unpinned items are auto-removed when this limit is exceeded. Default: 200",
        "paste_all_count": "Items per Ctrl+Shift+A:",
        "paste_all_count_tooltip": "Number of items pasted per Ctrl+Shift+A press. 0 (∞) = paste all remaining.",

        "search_placeholder": "Search…",
        "reset_queue": "Reset queue",
        "clear_tab": "Clear all",
        "pin_filter": "Pinned only",
        "collapse_all": "Collapse all",
        "expand_all": "Expand all",
        "ghost_mode": "Ghost mode",
        "settings": "Settings",
        "items_count": "{count} items",
        "ready": "Ready",

        "copied_ctrlv": "✓ Copied — Ctrl+V to paste",
        "pasted_next": "✓ Pasted — next: {preview}",
        "pasted_done": "✓ Pasted — queue empty",
        "queue_empty": "⚠ Queue empty",
        "queue_reset": "▶ Queue reset ({mode})",
        "skip_next": "⏭ Skipped — next: {preview}",
        "skip_done": "⏭ Skipped — queue empty",
        "cleared_tab": "Cleared: {tab}",
        "ghost_on": "Ghost mode: ON",
        "ghost_off": "Ghost mode: OFF",
        "pin_only": "Showing pinned items only",
        "show_all": "Showing all items",
        "paste_all_start": "▶ Batch paste: {count} items",
        "paste_all_stop": "⏹ Stop batch paste",
        "paste_all_stopped": "⏹ Batch paste stopped",
        "paste_all_progress": "⏳ Pasting {done}/{total} — next: {preview}",
        "paste_all_done": "✓ Pasted all {total} items",
        "paste_busy": "⚠ Paste in progress, please wait…",
        "paste_timeout": "⚠ Paste got stuck — auto-recovered",
        "words": "{count} words",

        "pin": "Pin",
        "unpin": "Unpin",
        "paste": "Paste",
        "view_image": "View image",
        "ocr_scan": "OCR scan",
        "open_explorer": "Open in Explorer",
        "copy": "Copy",
        "delete": "Delete",
        "expand": "Expand",
        "collapse": "Collapse",
        "start_from_here": "Start from here",
        "lines_more": "(+{count} lines)",

        "ctx_start_here": "▶ Start from here",
        "ctx_paste": "📋 Paste",
        "ctx_pin": "📌 Pin/Unpin",
        "ctx_copy": "📑 Copy",
        "ctx_view_image": "👁 View image",
        "ctx_ocr": "🔍 OCR scan",
        "ctx_open_explorer": "📂 Open in Explorer",
        "ctx_delete": "🗑️ Delete",

        "tray_show": "Show CyberClip",
        "tray_ghost": "Ghost mode",
        "tray_settings": "Settings",
        "tray_quit": "Quit",

        "empty_title": "Nothing here",
        "empty_subtitle": "Copy something to get started",

        # OCR
        "ocr_scanning": "Scanning text (OCR)…",
        "ocr_extracted": "OCR: {count} characters extracted",
        "ocr_no_text": "OCR: No text found",

        # Image viewer
        "img_viewer_title": "🖼  Image Viewer",
        "img_zoom_in": "Zoom in",
        "img_zoom_out": "Zoom out",
        "img_fit_window": "Fit to window",
        "img_actual_size": "100%",
        "img_load_error": "Cannot load image",

        # Choice menu
        "choice_paste_original": "Paste Original",
        "choice_paste_next": "Paste Next in Queue",
    },
}

_current_lang = "vi"


def set_language(lang: str):
    global _current_lang
    _current_lang = lang if lang in _STRINGS else "vi"


def get_language() -> str:
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Get translated string. Use keyword args for placeholders like {count}."""
    text = _STRINGS.get(_current_lang, _STRINGS["vi"]).get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text
