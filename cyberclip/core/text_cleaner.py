"""Text cleaner - strips formatting to plain text."""
import re
import html


def strip_html(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def strip_rtf(text: str) -> str:
    text = re.sub(r'\\[a-z]+\d*\s?', '', text)
    text = re.sub(r'[{}]', '', text)
    text = re.sub(r'\\\'[0-9a-f]{2}', '', text)
    return text.strip()


def to_plain_text(text: str) -> str:
    if text.strip().startswith('{\\rtf'):
        return strip_rtf(text)
    if '<' in text and '>' in text:
        cleaned = strip_html(text)
        if cleaned:
            return cleaned
    return text


def normalize_whitespace(text: str) -> str:
    lines = text.split('\n')
    lines = [' '.join(line.split()) for line in lines]
    return '\n'.join(lines)
