"""Color detector - detects and parses color codes."""
import re
import json
from typing import Optional, Tuple

HEX_RE = re.compile(r'^#(?P<hex>[0-9a-fA-F]{3,8})$')
RGB_RE = re.compile(
    r'^rgba?\(\s*(?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})\s*(?:,\s*(?P<a>[\d.]+)\s*)?\)$'
)
HSL_RE = re.compile(
    r'^hsla?\(\s*(?P<h>\d{1,3})\s*,\s*(?P<s>\d{1,3})%?\s*,\s*(?P<l>\d{1,3})%?\s*(?:,\s*(?P<a>[\d.]+)\s*)?\)$'
)


def detect_color(text: str) -> Optional[str]:
    text = text.strip()
    if HEX_RE.match(text) or RGB_RE.match(text) or HSL_RE.match(text):
        return text
    return None


def parse_color_to_rgb(color_str: str) -> Optional[Tuple[int, int, int]]:
    color_str = color_str.strip()

    m = HEX_RE.match(color_str)
    if m:
        h = m.group("hex")
        if len(h) == 3:
            r, g, b = int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)
        elif len(h) == 6:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        elif len(h) == 8:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        else:
            return None
        return r, g, b

    m = RGB_RE.match(color_str)
    if m:
        return int(m.group("r")), int(m.group("g")), int(m.group("b"))

    m = HSL_RE.match(color_str)
    if m:
        h, s, l = int(m.group("h")), int(m.group("s")), int(m.group("l"))
        return hsl_to_rgb(h, s, l)

    return None


def hsl_to_rgb(h: int, s: int, l: int) -> Tuple[int, int, int]:
    s /= 100
    l /= 100
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
