# Modified: [1.7, 2.3] LOG_DIR constant; [3.4] MAX_HISTORY_SIZE; [5.1] QUICK_PASTE_HOTKEY;
#           [6.1] kept for reference; misc new constants for Phases 1–6
"""Constants and configuration for CyberClip."""
import os

APP_NAME = "CyberClip"
APP_VERSION = "1.3.0"

# Paths
APP_DATA_DIR = os.path.join(os.getenv("APPDATA", ""), APP_NAME)
DB_PATH = os.path.join(APP_DATA_DIR, "cyberclip.db")
IMAGE_STORE_DIR = os.path.join(APP_DATA_DIR, ".images")
SETTINGS_PATH = os.path.join(APP_DATA_DIR, "settings.json")
LOG_DIR = os.path.join(APP_DATA_DIR, "logs")              # 2.3

# Limits
MAX_ITEMS_PER_TAB = 100
MAX_HISTORY_SIZE = 500          # 3.4 — global hard cap across all tabs
MAX_TEXT_PREVIEW = 200
GHOST_TYPE_DELAY_MS = 15
CHOICE_MENU_HOLD_MS = 500

# Clipboard item types
TYPE_TEXT = "text"
TYPE_IMAGE = "image"
TYPE_FILE = "file"
TYPE_URL = "url"
TYPE_COLOR = "color"
TYPE_EMAIL = "email"       # 5.3
TYPE_CODE = "code"         # 5.3
TYPE_SENSITIVE = "sensitive"  # 2.1

# Default hotkeys (global — work even when window is hidden)
DEFAULT_HOTKEYS = {
    "sequential_paste": "Ctrl+Shift+V",
    "paste_all": "Ctrl+Shift+A",
    "toggle_window": "Ctrl+Shift+C",
    "skip_item": "Ctrl+Shift+S",
    "ghost_mode": "Ctrl+Shift+G",
    "quick_paste": "Ctrl+Shift+Space",   # 5.1
}

# ── Modern Minimalist Palette ──
ACCENT = "#4F7CFF"
ACCENT_HOVER = "#6B91FF"
ACCENT_DIM = "rgba(79,124,255,0.10)"
ACCENT_BORDER = "rgba(79,124,255,0.25)"

SUCCESS = "#34C759"
DANGER_RED = "#FF453A"
WARNING_YELLOW = "#FFD60A"

DARK_BG = "#1C1C1E"
DARK_SURFACE = "#2C2C2E"
DARK_CARD = "#363638"
DARK_CARD_HOVER = "#3A3A3C"
GLASS_BG = "rgba(44, 44, 46, 0.92)"

TEXT_PRIMARY = "#F5F5F7"
TEXT_SECONDARY = "#A1A1A6"
TEXT_DIM = "#636366"

BORDER_DEFAULT = "rgba(255,255,255,0.08)"
BORDER_HOVER = "rgba(255,255,255,0.15)"

# Legacy aliases
NEON_CYAN = ACCENT
NEON_PURPLE = "#BF5AF2"
NEON_PINK = "#FF375F"
NEON_GREEN = SUCCESS
BORDER_GLOW = ACCENT

# URL tracking parameters to strip
TRACKING_PARAMS = [
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "dclid", "zanpid", "msclkid",
    "mc_cid", "mc_eid", "ref", "referrer",
    "_ga", "_gl", "yclid", "twclid",
]

# Blacklist defaults (password managers that set CF_ExcludeClipboardContent)
DEFAULT_BLACKLIST = [
    "1Password", "KeePass", "LastPass", "Bitwarden", "Dashlane",
    "KeePassXC", "RoboForm", "Enpass",
]

FONT_FAMILY = "FiraCode Nerd Font"
FONT_FAMILY_FALLBACK = "Segoe UI"

# Animation durations (ms)
ANIM_FAST = 150
ANIM_NORMAL = 250
ANIM_SLOW = 400

# Sensitive data patterns (2.1)
SENSITIVE_PATTERNS = {
    "credit_card": r'\b(?:\d[ -]?){13,16}\b',
    "password_label": r'(?i)(password|passwd|secret|token|api[_\-]?key)\s*[:=]\s*\S+',
}
SENSITIVE_MASK = "***REDACTED***"

# Image viewer zoom bounds (3.5)
ZOOM_MIN = 0.10   # 10 %
ZOOM_MAX = 5.00   # 500 %

# Search debounce (3.3)
SEARCH_DEBOUNCE_MS = 300

# Paste-all delay range (4.1)
PASTE_DELAY_MIN_MS = 50
PASTE_DELAY_MAX_MS = 1000
PASTE_DELAY_DEFAULT_MS = 150   # used by new Quick Paste popup

# Quick paste popup (5.1)
QUICK_PASTE_MAX_ITEMS = 10
