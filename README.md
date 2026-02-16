# CyberClip 📋

**Trình quản lý clipboard thông minh cho Windows** — sao chép nhiều mục, dán tuần tự theo thứ tự FIFO/LIFO, hỗ trợ ảnh, OCR, và nhiều tính năng khác.

![Windows](https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows)
![Python](https://img.shields.io/badge/Python-3.12-yellow?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ Tính năng chính

| Tính năng | Mô tả |
|-----------|-------|
| 📋 **Lịch sử clipboard** | Tự động lưu mọi thứ bạn sao chép (văn bản, ảnh, file, URL, mã màu) |
| 🔄 **Dán tuần tự (Magazine)** | FIFO hoặc LIFO — dán xong tự chuyển sang mục tiếp theo |
| 🖼️ **Hỗ trợ ảnh** | Xem thumbnail, phóng to/thu nhỏ, kéo thả |
| 🔍 **OCR** | Quét chữ từ ảnh (cần Tesseract) |
| 📌 **Ghim mục quan trọng** | Không bị xóa khi dọn dẹp |
| 🔎 **Tìm kiếm** | Tìm nhanh trong lịch sử |
| ⌨️ **Phím tắt toàn cục** | Ctrl+Shift+V dán tuần tự, tùy chỉnh được |
| 🎨 **Giao diện tối hiện đại** | Thiết kế minimalist, hỗ trợ 4K |
| 🇻🇳 **Tiếng Việt** | Giao diện hoàn toàn bằng tiếng Việt |

## 📥 Cài đặt

### Cách 1: Tải file .exe (Khuyên dùng)

1. Vào trang [Releases](../../releases)
2. Tải file `CyberClip.exe`
3. Chạy trực tiếp — không cần cài đặt gì thêm

> **Lưu ý:** Windows SmartScreen có thể cảnh báo vì file chưa được ký số. Nhấn "More info" → "Run anyway".

### Cách 2: Chạy từ source code

```bash
# Yêu cầu: Python 3.12+
git clone https://github.com/YOUR_USERNAME/CyberClip.git
cd CyberClip
pip install -r requirements.txt
python main.py
```

### Cách 3: Tự build exe

```bash
pip install pyinstaller
pyinstaller CyberClip.spec
# File exe sẽ ở thư mục dist/
```

## ⌨️ Phím tắt mặc định

| Phím tắt | Chức năng |
|----------|-----------|
| `Ctrl+Shift+V` | Dán tuần tự (dán & chuyển mục tiếp) |
| `Ctrl+Shift+S` | Hiện/Ẩn CyberClip |
| `Ctrl+Shift+N` | Bỏ qua mục, chuyển tiếp |
| `Ctrl+Shift+G` | Bật/Tắt chế độ ẩn |
| `Enter` | Sao chép mục đã chọn |
| `↑ / ↓` | Di chuyển giữa các mục |
| `Delete` | Xóa mục |
| `Ctrl+P` | Ghim / Bỏ ghim |
| `Ctrl+F` | Tìm kiếm |
| `Escape` | Ẩn cửa sổ |

> Tất cả phím tắt toàn cục có thể thay đổi trong Cài đặt → Phím tắt.

## 🖼️ Cấu trúc dự án

```
CyberClip/
├── main.py                 # Entry point
├── CyberClip.spec          # PyInstaller config
├── requirements.txt        # Dependencies
├── assets/
│   └── icon.ico           # App icon
├── cyberclip/
│   ├── app.py             # Application bootstrap
│   ├── core/              # Business logic
│   │   ├── clipboard_monitor.py
│   │   ├── magazine.py
│   │   ├── global_hotkeys.py
│   │   ├── safety_net.py
│   │   ├── ocr_scanner.py
│   │   ├── text_cleaner.py
│   │   ├── photo_fixer.py
│   │   ├── link_cleaner.py
│   │   ├── color_detector.py
│   │   └── app_detector.py
│   ├── gui/               # UI components
│   │   ├── main_window.py
│   │   ├── item_widget.py
│   │   ├── image_viewer.py
│   │   ├── hud_widget.py
│   │   ├── tab_bar.py
│   │   ├── choice_menu.py
│   │   ├── settings_dialog.py
│   │   └── styles.py
│   ├── storage/           # Database & file storage
│   │   ├── database.py
│   │   ├── image_store.py
│   │   └── models.py
│   └── utils/             # Utilities
│       ├── constants.py
│       └── win32_helpers.py
└── version_info.py
```

## 🛠️ Công nghệ

- **Python 3.12** + **PyQt6** — GUI framework
- **pywin32** — Windows API integration
- **Pillow** — Xử lý ảnh
- **SQLite** — Lưu trữ dữ liệu
- **PyInstaller** — Build standalone exe

## 📝 License

MIT License — xem file [LICENSE](LICENSE).
