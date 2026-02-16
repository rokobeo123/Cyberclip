# CyberClip

**Smart clipboard manager for Windows** — copy multiple items, paste sequentially in FIFO/LIFO order, with image support, and more.

Supports **English** and **Vietnamese** (Tiếng Việt).

---

## Features

| Feature | Description |
|---------|-------------|
| Clipboard History | Automatically saves everything you copy (text, images, files, URLs, color codes) |
| Sequential Paste (Magazine) | FIFO or LIFO — paste one item and auto-advance to the next |
| Image Support | View thumbnails, zoom in/out, copy images |
| OCR | Extract text from images (requires Tesseract) |
| Pin Important Items | Pinned items are never deleted during cleanup |
| Search | Quickly find items in your history |
| Global Hotkeys | Ctrl+Shift+V for sequential paste, fully customizable |
| Modern Dark UI | Minimalist design, supports 4K displays |
| Bilingual | English and Vietnamese interface |
| Ghost Mode | Instantly stop recording clipboard activity |
| Drag & Drop | Reorder clips by dragging them |
| Paste All | Paste entire queue at once with one hotkey |

## Installation

### Option 1: Download .exe (Recommended)

1. Go to the [Releases](../../releases) page
2. Download `CyberClip.exe`
3. Run it directly — no installation needed

> **Note:** Windows SmartScreen may warn because the file is not digitally signed. Click "More info" → "Run anyway".

### Option 2: Run from source

```bash
# Requires Python 3.12+
git clone https://github.com/YOUR_USERNAME/CyberClip.git
cd CyberClip
pip install -r requirements.txt
python main.py
```

### Option 3: Build exe yourself

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name CyberClip --add-data "cyberclip;cyberclip" main.py
# The exe will be in the dist/ folder
```

## Default Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+V` | Sequential paste (paste & advance) |
| `Ctrl+Shift+A` | Paste all remaining items |
| `Ctrl+Shift+S` | Show / Hide CyberClip |
| `Ctrl+Shift+N` | Skip to next item |
| `Ctrl+Shift+G` | Toggle ghost mode |
| `Enter` | Copy selected item |
| `↑ / ↓` | Navigate between items |
| `Delete` | Delete item |
| `Ctrl+P` | Pin / Unpin |
| `Ctrl+F` | Search |
| `Escape` | Hide window / Stop batch paste |

> All global hotkeys can be customized in Settings → Hotkeys.

## Project Structure

```
CyberClip/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── cyberclip/
│   ├── app.py             # Application bootstrap
│   ├── core/              # Business logic
│   │   ├── clipboard_monitor.py
│   │   ├── magazine.py
│   │   ├── global_hotkeys.py
│   │   ├── safety_net.py
│   │   ├── ocr_scanner.py
│   │   └── ...
│   ├── gui/               # UI components
│   │   ├── main_window.py
│   │   ├── item_widget.py
│   │   ├── image_viewer.py
│   │   ├── settings_dialog.py
│   │   ├── styles.py
│   │   └── ...
│   ├── storage/           # Database & file storage
│   │   ├── database.py
│   │   ├── image_store.py
│   │   └── models.py
│   └── utils/             # Utilities
│       ├── constants.py
│       ├── i18n.py
│       └── win32_helpers.py
└── .github/workflows/
    └── release.yml         # Auto-build on tag push
```

## Tech Stack

- **Python 3.12** + **PyQt6** — GUI framework
- **pywin32** — Windows API integration
- **Pillow** — Image processing
- **SQLite** — Data storage
- **PyInstaller** — Standalone exe packaging

## License

MIT License — see [LICENSE](LICENSE).
