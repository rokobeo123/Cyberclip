# Modified: [2.1] New module — detects and masks sensitive clipboard content
#           (credit card numbers, password/token labels) before saving to history.
"""Sensitive data detection and masking for CyberClip (Phase 2.1)."""
import re
from typing import Tuple

from cyberclip.utils.constants import SENSITIVE_PATTERNS, SENSITIVE_MASK

# Pre-compiled patterns
_CREDIT_CARD_RE = re.compile(SENSITIVE_PATTERNS["credit_card"])
_PASSWORD_LABEL_RE = re.compile(SENSITIVE_PATTERNS["password_label"])

# Extra lightweight patterns
_API_KEY_BARE_RE = re.compile(
    r'(?i)\b(?:api[_\-]?key|token|secret|password|passwd)\b\s*[:=]\s*\S{6,}',
)
# Common "Bearer <token>" patterns
_BEARER_RE = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b')

# Minimum text length to bother checking (short snippets are very unlikely to be secrets)
_MIN_CHECK_LEN = 6


def is_sensitive(text: str) -> bool:
    """
    Return True if *text* appears to contain sensitive information that should
    not be stored in plain form.

    Checks:
    - Credit card numbers (13–16 contiguous digits, optionally spaced/dashed)
    - Password / token assignment patterns: ``password=xxx``, ``token: yyy``, …
    - Bearer tokens
    - Bare API-key label patterns
    """
    if not text or len(text) < _MIN_CHECK_LEN:
        return False

    if _CREDIT_CARD_RE.search(text):
        # Luhn-like sanity: reject pure dates / phone numbers
        digits_only = re.sub(r'\D', '', text)
        if 13 <= len(digits_only) <= 19:
            return True

    if _PASSWORD_LABEL_RE.search(text):
        return True

    if _API_KEY_BARE_RE.search(text):
        return True

    if _BEARER_RE.search(text):
        return True

    return False


def mask(text: str) -> str:
    """
    Return a redacted version of *text* suitable for display / storage.
    Replaces matched sensitive fragments with ``SENSITIVE_MASK``; falls back
    to returning the full mask if the entire string is deemed sensitive.
    """
    if not text:
        return text

    result = text

    # Replace credit card numbers
    def _mask_cc(m):
        raw = m.group(0)
        digits = re.sub(r'\D', '', raw)
        if 13 <= len(digits) <= 19:
            return SENSITIVE_MASK
        return raw

    result = _CREDIT_CARD_RE.sub(_mask_cc, result)

    # Replace password / token assignments: keep the label, mask the value
    def _mask_label(m):
        label = m.group(1)
        return f"{label}={SENSITIVE_MASK}"

    result = _PASSWORD_LABEL_RE.sub(_mask_label, result)
    result = _API_KEY_BARE_RE.sub(lambda _: SENSITIVE_MASK, result)
    result = _BEARER_RE.sub(f"Bearer {SENSITIVE_MASK}", result)

    return result


def detect(text: str) -> Tuple[bool, str]:
    """
    Convenience function: return *(is_sensitive, display_text)*.

    If sensitive, *display_text* is the masked form.  Otherwise it equals *text*.
    """
    if is_sensitive(text):
        return True, mask(text)
    return False, text
