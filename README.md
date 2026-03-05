# CyberClip

**Smart clipboard manager for Windows** — copy multiple items, paste sequentially in FIFO/LIFO order, with image support, sensitive-data masking, text transforms, and more.

Supports **English** and **Vietnamese** (Tiếng Việt).

---

## What's New in v1.3.0

- 🔒 **Sensitive Data Protection** — credit card numbers and password/token patterns are auto-detected, masked, and stored safely
- ⚡ **Quick Paste Popup** — `Ctrl+Shift+Space` opens a compact floating list at your cursor; press 1–9 or click to paste instantly
- 🔄 **Text Transforms** — right-click any text clip to UPPERCASE / lowercase / Title Case / URL encode / Base64 / JSON pretty-print / and 8 more
- 👻 **Ghost Mode Indicator** — tray icon turns gray when ghost mode is active
- 🏷️ **Smart Type Detection** — clips are tagged as URL, email, code, color, or file path with matching icons
- 📌 **Snippets** — save any clip as a permanent snippet with a trigger keyword
- 📤 **Export / Import** — backup and restore clipboard history as JSON (images included as base64)
- 🚫 **Per-App Exclusion** — block specific apps (e.g. `KeePass.exe`) from being recorded
- 🖼️ **Image Viewer Zoom** — clamped to 10%–500% for usability
- 🔢 **Queue Position in Tray** — tooltip shows `[2/7]` current position
- ✅ **Batch Paste Confirm** — dialog when pasting more than 10 items
- 🛡️ **SQLite WAL Mode + Integrity Check** — auto-backup and recreate on corruption
- 🔧 **Thread Safety** — all shared state protected with `threading.Lock()`
- 📜 **Crash Logging** — rotating logs written to `%APPDATA%\CyberClip\logs\`

---

## Features

| Feature | Description |
|---------|-------------|
| Clipboard History | Automatically saves text, images, files, URLs, colors, emails, code |
| Sequential Paste (Magazine) | FIFO or LIFO — paste one item and auto-advance to the next |
| Quick Paste Popup | `Ctrl+Shift+Space` — floating list at cursor, press 1–9 to paste |
| Text Transforms | 14 transforms: case, trim, URL/Base64 encode, JSON format, dedup lines |
| Sensitive Data Masking | Credit cards and password patterns auto-masked before saving |
| Snippets | Save clips as named snippets with a trigger keyword |
| Export / Import | Full history backup to JSON with base64 images |
| Image Support | Thumbnail preview, full viewer with 10%–500% zoom, OCR |
| Pin Items | Pinned items survive cleanup and queue resets |
| Search | 300ms debounced search across all items |
| Global Hotkeys | Fully customizable; conflict detection with tray notification |
| Ghost Mode | Stop recording; tray icon changes to indicate state |
| Drag & Drop | Reorder clips; order persisted to database |
| Per-App Exclusion | Block process names (e.g. `1password.exe`) from being recorded |
| DPI Aware | Per-Monitor V2 DPI awareness for 4K / 150% / 200% scaling |
| Bilingual | English and Vietnamese interface |

---

## Installation

### Option 1: Download .exe (Recommended)

1. Go to the [Releases](../../releases) page
2. Download `CyberClip.exe`
3. Run it directly — no installation needed

> **Note:** Windows SmartScreen may warn because the file is not digitally signed. Click "More info" → "Run anyway".

### Option 2: Run from source

```bash
# Requires Python 3.12+
git clone https://github.com/rokobeo123/Cyberclip.git
cd Cyberclip
pip install -r requirements.txt
python main.py
```

### Option 3: Build exe yourself

```bash
pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name CyberClip --add-data "cyberclip;cyberclip" main.py
# The exe will be in the dist/ folder
```

---

## Default Hotkeys

| Hotkey | Action |
|--------|--------|
| `Ctrl+Shift+V` | Sequential paste (paste & advance) |
| `Ctrl+Shift+A` | Paste all remaining items |
| `Ctrl+Shift+C` | Show / Hide CyberClip |
| `Ctrl+Shift+S` | Skip to next item |
| `Ctrl+Shift+G` | Toggle ghost mode |
| `Ctrl+Shift+Space` | **Quick Paste Popup** (new) |
| `Enter` | Copy selected item |
| `↑ / ↓` | Navigate between items |
| `Delete` | Delete item |
| `Ctrl+P` | Pin / Unpin |
| `Ctrl+F` | Search |
| `Escape` | Hide window / Stop batch paste |

> All global hotkeys can be customized in **Settings → Hotkeys**.

---

## Project Structure

```
CyberClip/
├── main.py                 # Entry point
├── requirements.txt        # Pinned dependencies
├── cyberclip/
│   ├── app.py             # Bootstrap: DPI, logging, ServiceLocator, startup registry
│   ├── core/
│   │   ├── clipboard_monitor.py   # Thread-safe polling, sensitive detection, exclusions
│   │   ├── magazine.py            # FIFO/LIFO queue
│   │   ├── global_hotkeys.py      # Win32 RegisterHotKey with conflict detection
│   │   ├── ocr_scanner.py         # Tesseract via QThread worker (10s timeout)
│   │   └── ...
│   ├── gui/
│   │   ├── main_window.py         # Primary UI
│   │   ├── item_widget.py         # Per-clip card with transforms & sensitive display
│   │   ├── image_viewer.py        # Zoom 10%–500%, pan
│   │   ├── quick_paste_popup.py   # Frameless popup at cursor (new)
│   │   └── ...
│   ├── storage/
│   │   ├── database.py            # WAL, integrity check, snippets, exclusions
│   │   ├── image_store.py         # Orphan cleanup on startup
│   │   └── models.py              # ClipboardItem, Snippet, AppExclusion
│   └── utils/
│       ├── constants.py
│       ├── i18n.py                # EN + VI strings for all features
│       ├── sensitive_detector.py  # Regex-based sensitive data detection (new)
│       └── text_transforms.py     # 14 text transform functions (new)
└── .github/workflows/
    └── release.yml                # Auto-build on tag push
```

---

## Tech Stack

- **Python 3.12** + **PyQt6 6.7.0** — GUI framework
- **pywin32 306** — Windows API (hotkeys, clipboard, session events)
- **Pillow 10.3.0** — Image processing
- **pytesseract 0.3.10** — OCR (optional, requires Tesseract installed)
- **SQLite** — Embedded database with WAL mode
- **PyInstaller** — Standalone exe packaging

---

## License

MIT License — see [LICENSE](LICENSE).
