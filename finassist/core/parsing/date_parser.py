from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as dateutil_parser

KNOWN_FORMATS = [
    "%d/%m/%y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%d-%m-%Y",
    "%d-%b-%Y",
    "%d %b %y",
    "%Y-%m-%d",
]


def parse_date(
    date_str: str | None,
    primary_format: str | None = None,
    fallback_format: str | None = None,
) -> date | None:
    if not date_str:
        return None

    cleaned = str(date_str).strip()
    if cleaned in ("", "nan", "None", "-"):
        return None
    cleaned = re.sub(r"\s+", " ", cleaned)

    formats: list[str] = []
    if primary_format:
        formats.append(primary_format)
    if fallback_format:
        formats.append(fallback_format)
    formats.extend(KNOWN_FORMATS)

    seen: set[str] = set()
    unique: list[str] = []
    for f in formats:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    for fmt in unique:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    try:
        return dateutil_parser.parse(cleaned, dayfirst=True).date()
    except (ValueError, TypeError):
        return None


def looks_like_date(value: str) -> bool:
    if not value:
        return False
    cleaned = str(value).strip()
    if not cleaned or cleaned in ("nan", "None", "-", ""):
        return False
    return bool(re.match(r"^\d{1,2}[\s/\-]", cleaned))
