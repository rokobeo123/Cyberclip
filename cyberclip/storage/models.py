"""Data models for CyberClip clipboard items."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ClipboardItem:
    id: Optional[int] = None
    content_type: str = "text"  # text, image, file, url, color
    text_content: str = ""
    image_path: str = ""
    source_app: str = ""
    tab: str = "General"
    pinned: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    extra_data: str = ""  # JSON for color codes, cleaned URLs, etc.

    @property
    def preview(self):
        if self.content_type == "image":
            return "[Image]"
        if self.content_type == "file":
            return self.text_content
        text = self.text_content or ""
        if len(text) > 200:
            return text[:200] + "…"
        return text

    @property
    def is_empty(self):
        return not self.text_content and not self.image_path


@dataclass
class TabRule:
    id: Optional[int] = None
    app_pattern: str = ""
    tab_name: str = "General"
    enabled: bool = True


@dataclass
class AppSettings:
    picking_style: str = "FIFO"  # FIFO or LIFO
    ghost_mode: bool = False
    strip_formatting: bool = False
    auto_enter: bool = False
    auto_tab: bool = False
    super_paste_enabled: bool = False
    ghost_type_speed: int = 15
    theme: str = "cyberpunk"
    blacklist: list = field(default_factory=list)
    hotkeys: dict = field(default_factory=dict)
    tab_rules: list = field(default_factory=list)
    window_x: int = -1
    window_y: int = -1
    window_width: int = 420
    window_height: int = 680
