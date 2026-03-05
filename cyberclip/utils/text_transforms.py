# Modified: [5.2] New module — all text transform functions for right-click submenu.
#           Each transform takes a str and returns a new str (never mutates original).
"""Text transform functions for CyberClip (Phase 5.2)."""
import json
import re
import urllib.parse
import base64
from typing import Callable


# ── Individual transforms ─────────────────────────────────────────────────────

def to_uppercase(text: str) -> str:
    return text.upper()


def to_lowercase(text: str) -> str:
    return text.lower()


def to_title_case(text: str) -> str:
    return text.title()


def to_sentence_case(text: str) -> str:
    if not text:
        return text
    result = []
    capitalize_next = True
    for char in text:
        if capitalize_next and char.isalpha():
            result.append(char.upper())
            capitalize_next = False
        else:
            result.append(char.lower() if not capitalize_next else char)
        if char in '.!?':
            capitalize_next = True
    return ''.join(result)


def trim_whitespace(text: str) -> str:
    return text.strip()


def remove_extra_spaces(text: str) -> str:
    """Replace multiple consecutive whitespace (within lines) with a single space."""
    lines = text.splitlines()
    return '\n'.join(re.sub(r'[ \t]+', ' ', line) for line in lines)


def join_lines(text: str) -> str:
    """Join all lines into a single line separated by a space."""
    return ' '.join(line.strip() for line in text.splitlines() if line.strip())


def url_encode(text: str) -> str:
    return urllib.parse.quote(text, safe='')


def url_decode(text: str) -> str:
    try:
        return urllib.parse.unquote(text)
    except Exception:
        return text


def base64_encode(text: str) -> str:
    try:
        return base64.b64encode(text.encode('utf-8')).decode('ascii')
    except Exception:
        return text


def base64_decode(text: str) -> str:
    try:
        # Handle padding
        missing = len(text) % 4
        if missing:
            text += '=' * (4 - missing)
        return base64.b64decode(text).decode('utf-8', errors='replace')
    except Exception:
        return text


def json_format(text: str) -> str:
    """Pretty-print JSON."""
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except json.JSONDecodeError:
        return text


def json_minify(text: str) -> str:
    """Minify JSON."""
    try:
        return json.dumps(json.loads(text), separators=(',', ':'), ensure_ascii=False)
    except json.JSONDecodeError:
        return text


def remove_duplicate_lines(text: str) -> str:
    seen = set()
    result = []
    for line in text.splitlines():
        if line not in seen:
            seen.add(line)
            result.append(line)
    return '\n'.join(result)


# ── Registry of all transforms with i18n keys ─────────────────────────────────

# List of (i18n_key, callable) in display order
TRANSFORMS: list[tuple[str, Callable[[str], str]]] = [
    ("transform_uppercase",     to_uppercase),
    ("transform_lowercase",     to_lowercase),
    ("transform_titlecase",     to_title_case),
    ("transform_sentencecase",  to_sentence_case),
    ("transform_trim",          trim_whitespace),
    ("transform_remove_spaces", remove_extra_spaces),
    ("transform_join_lines",    join_lines),
    ("transform_url_encode",    url_encode),
    ("transform_url_decode",    url_decode),
    ("transform_base64_encode", base64_encode),
    ("transform_base64_decode", base64_decode),
    ("transform_json_format",   json_format),
    ("transform_json_minify",   json_minify),
    ("transform_dedup_lines",   remove_duplicate_lines),
]


def apply(transform_key: str, text: str) -> str:
    """Apply a transform by its i18n key. Returns original text if key not found."""
    for key, fn in TRANSFORMS:
        if key == transform_key:
            try:
                return fn(text)
            except Exception:
                return text
    return text
