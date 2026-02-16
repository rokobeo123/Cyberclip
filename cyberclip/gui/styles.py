"""Modern minimalist QSS stylesheet for CyberClip."""
from cyberclip.utils.constants import (
    ACCENT, ACCENT_HOVER, ACCENT_DIM, ACCENT_BORDER,
    NEON_PURPLE, SUCCESS, DANGER_RED, WARNING_YELLOW,
    DARK_BG, DARK_SURFACE, DARK_CARD, DARK_CARD_HOVER,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM,
    BORDER_DEFAULT, BORDER_HOVER,
    FONT_FAMILY, FONT_FAMILY_FALLBACK,
    ANIM_FAST, ANIM_NORMAL,
)

CYBERPUNK_QSS = f"""
/* ═══════════════════════════════════════════════════════
   CYBERCLIP — Modern Minimalist Clipboard Manager
   Clean dark surfaces · soft blue accent · smooth UX
   ═══════════════════════════════════════════════════════ */

* {{
    font-family: "{FONT_FAMILY}", "{FONT_FAMILY_FALLBACK}", "Segoe UI", sans-serif;
    font-size: 12px;
    color: {TEXT_PRIMARY};
    outline: none;
}}

/* ── Main Window ─────────────────────────────────────── */
QMainWindow, #CyberClipMain {{
    background-color: {DARK_BG};
}}

/* ── Title Bar ───────────────────────────────────────── */
#TitleBar {{
    background: {DARK_BG};
    border-bottom: 1px solid {BORDER_DEFAULT};
}}

#TitleLabel {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    letter-spacing: 1px;
}}

#TitleButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 14px;
    padding: 4px 8px;
    border-radius: 6px;
}}
#TitleButton:hover {{
    background: rgba(255,255,255,0.08);
    color: {TEXT_PRIMARY};
}}

#CloseButton {{
    background: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 14px;
    padding: 4px 8px;
    border-radius: 6px;
}}
#CloseButton:hover {{
    background: rgba(255,69,58,0.18);
    color: {DANGER_RED};
}}

/* ── Search Bar ──────────────────────────────────────── */
#SearchBar {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 10px;
    padding: 8px 12px 8px 4px;
    font-size: 12px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_DIM};
}}
#SearchBar:focus {{
    border: 1px solid {ACCENT_BORDER};
}}

/* ── Tab Bar ─────────────────────────────────────────── */
#TabBar {{
    background: transparent;
    border: none;
    padding: 2px 8px;
}}

#TabButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 14px;
    font-size: 11px;
    color: {TEXT_SECONDARY};
    margin: 0 2px;
}}
#TabButton:hover {{
    background: rgba(255,255,255,0.05);
    color: {TEXT_PRIMARY};
}}
#TabButton[active="true"] {{
    background: {ACCENT_DIM};
    color: {ACCENT};
    border-color: {ACCENT_BORDER};
    font-weight: 600;
}}

/* ── Toolbar ─────────────────────────────────────────── */
#Toolbar {{
    background: transparent;
    border-bottom: 1px solid {BORDER_DEFAULT};
    padding: 4px 8px;
}}

#ToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 5px 10px;
    font-size: 11px;
    color: {TEXT_SECONDARY};
}}
#ToolButton:hover {{
    background: rgba(255,255,255,0.06);
    color: {TEXT_PRIMARY};
}}
#ToolButton:checked {{
    background: {ACCENT_DIM};
    color: {ACCENT};
    border-color: {ACCENT_BORDER};
}}
#ToolButton[danger="true"]:hover {{
    background: rgba(255,69,58,0.10);
    color: {DANGER_RED};
}}

/* ── Clipboard Item Cards ────────────────────────────── */
#ClipCard {{
    background: {DARK_CARD};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 12px;
    padding: 0px;
    margin: 2px 0;
}}
#ClipCard:hover {{
    background: {DARK_CARD_HOVER};
    border-color: {BORDER_HOVER};
}}

#ClipCard[pinned="true"] {{
    border-left: 3px solid {NEON_PURPLE};
}}

#ClipCard[selected="true"] {{
    border-color: {ACCENT_BORDER};
    background: {ACCENT_DIM};
}}

/* Magazine active (next item to paste) */
#ClipCard[magazine_active="true"] {{
    border-left: 3px solid {ACCENT};
    background: {ACCENT_DIM};
}}

/* Drop target highlight */
#ClipCard[drop_target="true"] {{
    border-top: 2px solid {ACCENT};
}}

#ClipContent {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    padding: 2px 0;
    background: transparent;
    border: none;
}}

#ClipMeta {{
    color: {TEXT_DIM};
    font-size: 10px;
    background: transparent;
    border: none;
}}

#ClipTypeIcon {{
    color: {ACCENT};
    font-size: 14px;
    background: {ACCENT_DIM};
    border-radius: 8px;
    padding: 4px;
    min-width: 24px; min-height: 24px;
    max-width: 24px; max-height: 24px;
}}

#ClipAction {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
    font-size: 13px;
    padding: 3px 6px;
    border-radius: 6px;
}}
#ClipAction:hover {{
    background: rgba(255,255,255,0.06);
    color: {TEXT_PRIMARY};
}}

#PinButton {{
    background: transparent;
    border: none;
    color: {TEXT_DIM};
    font-size: 13px;
    padding: 3px 6px;
    border-radius: 6px;
}}
#PinButton:hover {{
    background: rgba(191,90,242,0.10);
    color: {NEON_PURPLE};
}}
#PinButton[pinned="true"] {{
    color: {NEON_PURPLE};
}}

/* ── Queue Position Badge ────────────────────────────── */
#QueueBadge {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 0;
}}

/* ── Color Swatch ────────────────────────────────────── */
#ColorSwatch {{
    border-radius: 6px;
    border: 1px solid {BORDER_DEFAULT};
    min-width: 32px;
    min-height: 20px;
    max-height: 20px;
}}

/* ── Scroll Area ─────────────────────────────────────── */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 4px 1px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: rgba(255,255,255,0.10);
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(255,255,255,0.20);
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0px;
}}
QScrollBar:horizontal {{ height: 0px; }}

/* ── Status Bar / Footer ─────────────────────────────── */
#StatusBar {{
    background: {DARK_BG};
    border-top: 1px solid {BORDER_DEFAULT};
    padding: 4px 12px;
}}
#StatusLabel {{
    color: {TEXT_DIM};
    font-size: 10px;
}}
#MagazineCounter {{
    color: {ACCENT};
    font-size: 11px;
    font-weight: bold;
}}

/* ── Ghost Mode Indicator ────────────────────────────── */
#GhostIndicator {{
    color: {NEON_PURPLE};
    font-size: 10px;
    background: rgba(191,90,242,0.08);
    border: 1px solid rgba(191,90,242,0.20);
    border-radius: 6px;
    padding: 2px 8px;
}}

/* ── Popup / Choice Menu ─────────────────────────────── */
#ChoiceMenu {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_HOVER};
    border-radius: 12px;
    padding: 4px;
}}
#ChoiceItem {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT_PRIMARY};
    text-align: left;
    font-size: 12px;
}}
#ChoiceItem:hover {{
    background: rgba(255,255,255,0.06);
}}

/* ── HUD Widget ──────────────────────────────────────── */
#HUD {{
    background: rgba(28, 28, 30, 0.88);
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 10px;
    padding: 6px 12px;
}}
#HUDLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}

/* ── Tooltip ─────────────────────────────────────────── */
QToolTip {{
    background: {DARK_SURFACE};
    color: {TEXT_PRIMARY};
    border: 1px solid {BORDER_HOVER};
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* ── Context Menu ────────────────────────────────────── */
QMenu {{
    background: #2C2C2E;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 4px;
}}
QMenu::item {{
    background: transparent;
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    margin: 1px 4px;
    color: {TEXT_PRIMARY};
}}
QMenu::item:selected {{
    background: rgba(79,124,255,0.18);
    color: {TEXT_PRIMARY};
}}
QMenu::separator {{
    height: 1px;
    background: rgba(255,255,255,0.08);
    margin: 4px 8px;
}}

/* ── Settings Dialog ─────────────────────────────────── */
QDialog {{
    background: {DARK_BG};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 14px;
}}

QLabel {{
    background: transparent;
    color: {TEXT_PRIMARY};
}}

QLineEdit {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus {{
    border-color: {ACCENT_BORDER};
}}

QComboBox {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 6px 10px;
    color: {TEXT_PRIMARY};
    min-width: 100px;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    image: none;
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_HOVER};
    border-radius: 8px;
    selection-background-color: {ACCENT_DIM};
    outline: none;
}}

QPushButton {{
    background: {ACCENT_DIM};
    border: 1px solid {ACCENT_BORDER};
    border-radius: 8px;
    padding: 7px 18px;
    color: {ACCENT};
    font-weight: 600;
}}
QPushButton:hover {{
    background: rgba(79,124,255,0.18);
    border-color: rgba(79,124,255,0.40);
}}
QPushButton:pressed {{
    background: rgba(79,124,255,0.25);
}}
QPushButton[danger="true"] {{
    color: {DANGER_RED};
    border-color: rgba(255,69,58,0.18);
    background: rgba(255,69,58,0.06);
}}
QPushButton[danger="true"]:hover {{
    background: rgba(255,69,58,0.14);
    border-color: rgba(255,69,58,0.35);
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT_PRIMARY};
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid rgba(255,255,255,0.15);
    background: {DARK_SURFACE};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT_BORDER};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:unchecked {{
    background: {DARK_SURFACE};
}}

QSpinBox {{
    background: {DARK_SURFACE};
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    padding: 4px 8px;
    color: {TEXT_PRIMARY};
}}

QGroupBox {{
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 16px;
    color: {TEXT_SECONDARY};
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}}

/* ── Empty State ─────────────────────────────────────── */
#EmptyState {{
    color: {TEXT_DIM};
    font-size: 13px;
    background: transparent;
}}
#EmptyIcon {{
    font-size: 36px;
    color: rgba(255,255,255,0.08);
    background: transparent;
}}

/* ── Tab Widget (Settings) ───────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {BORDER_DEFAULT};
    border-radius: 8px;
    background: {DARK_SURFACE};
}}
QTabBar::tab {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 6px 14px;
    margin: 2px;
    color: {TEXT_SECONDARY};
}}
QTabBar::tab:selected {{
    background: {ACCENT_DIM};
    color: {ACCENT};
    border-color: {ACCENT_BORDER};
}}
QTabBar::tab:hover:!selected {{
    background: rgba(255,255,255,0.04);
    color: {TEXT_PRIMARY};
}}
"""
