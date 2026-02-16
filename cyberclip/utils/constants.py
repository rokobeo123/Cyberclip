"""Constants and configuration for CyberClip."""
import os

APP_NAME = "CyberClip"
APP_VERSION = "1.2.0"

# Paths
APP_DATA_DIR = os.path.join(os.getenv("APPDATA", ""), APP_NAME)
DB_PATH = os.path.join(APP_DATA_DIR, "cyberclip.db")
IMAGE_STORE_DIR = os.path.join(APP_DATA_DIR, ".images")
SETTINGS_PATH = os.path.join(APP_DATA_DIR, "settings.json")

# Limits
MAX_ITEMS_PER_TAB = 100
MAX_TEXT_PREVIEW = 200
GHOST_TYPE_DELAY_MS = 15
CHOICE_MENU_HOLD_MS = 500

# Clipboard item types
TYPE_TEXT = "text"
TYPE_IMAGE = "image"
TYPE_FILE = "file"
TYPE_URL = "url"
TYPE_COLOR = "color"

# Default hotkeys (global — work even when window is hidden)
DEFAULT_HOTKEYS = {
    "sequential_paste": "Ctrl+Shift+V",
    "paste_all": "Ctrl+Shift+A",
    "toggle_window": "Ctrl+Shift+C",
    "skip_item": "Ctrl+Shift+S",
    "ghost_mode": "Ctrl+Shift+G",
}

# ── Modern Minimalist Palette ──
# Primary accent
ACCENT = "#4F7CFF"          # Soft blue
ACCENT_HOVER = "#6B91FF"
ACCENT_DIM = "rgba(79,124,255,0.10)"
ACCENT_BORDER = "rgba(79,124,255,0.25)"

# Semantic
SUCCESS = "#34C759"
DANGER_RED = "#FF453A"
WARNING_YELLOW = "#FFD60A"

# Surfaces (dark mode)
DARK_BG = "#1C1C1E"
DARK_SURFACE = "#2C2C2E"
DARK_CARD = "#363638"
DARK_CARD_HOVER = "#3A3A3C"
GLASS_BG = "rgba(44, 44, 46, 0.92)"

# Text
TEXT_PRIMARY = "#F5F5F7"
TEXT_SECONDARY = "#A1A1A6"
TEXT_DIM = "#636366"

# Borders
BORDER_DEFAULT = "rgba(255,255,255,0.08)"
BORDER_HOVER = "rgba(255,255,255,0.15)"

# Legacy aliases (keep so existing code doesn't break)
NEON_CYAN = ACCENT
NEON_PURPLE = "#BF5AF2"   # still used for pin badge
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

# Blacklist defaults
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
