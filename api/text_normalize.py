from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")


def normalize_for_keyword(text: str) -> str:
    value = unicodedata.normalize("NFKC", text or "")
    value = value.casefold()
    value = _WHITESPACE_RE.sub("", value)
    return value.strip()
