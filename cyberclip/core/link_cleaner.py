"""Link cleaner - strips tracking parameters from URLs."""
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from cyberclip.utils.constants import TRACKING_PARAMS


def clean_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items()
                   if k.lower() not in TRACKING_PARAMS}
        new_query = urlencode(cleaned, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url


def is_url(text: str) -> bool:
    try:
        result = urlparse(text)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False
