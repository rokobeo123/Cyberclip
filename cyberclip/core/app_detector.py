"""App detector - detect foreground application for tab switching."""
import re
from typing import Optional

from cyberclip.utils.win32_helpers import get_foreground_window_info
from cyberclip.storage.models import TabRule


class AppDetector:
    def __init__(self):
        self._rules = []
        self._last_app = ""

    def set_rules(self, rules: list):
        self._rules = [r for r in rules if r.enabled]

    def detect_tab(self) -> Optional[str]:
        try:
            _, title, exe = get_foreground_window_info()
            app_str = f"{exe or ''} {title or ''}".lower()

            if app_str == self._last_app:
                return None
            self._last_app = app_str

            for rule in self._rules:
                pattern = rule.app_pattern.lower()
                if pattern in app_str or re.search(pattern, app_str):
                    return rule.tab_name
        except Exception:
            pass
        return None

    def get_current_app(self) -> str:
        try:
            _, title, exe = get_foreground_window_info()
            return exe or title or ""
        except Exception:
            return ""
