from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_indian_amount(amount_str: str | None) -> Decimal:
    """Parse Indian-formatted currency amounts. Returns Decimal."""
    if not amount_str:
        return Decimal("0.00")

    cleaned = str(amount_str).strip()
    if cleaned in ("", "-", "nan", "None", "null", "—", "–"):
        return Decimal("0.00")

    is_negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        is_negative = True
        cleaned = cleaned[1:-1].strip()

    if cleaned.startswith("-"):
        is_negative = True
        cleaned = cleaned[1:].strip()

    upper = cleaned.upper()
    if upper.endswith("DR"):
        is_negative = True
        cleaned = cleaned[:-2].strip()
    elif upper.endswith("CR"):
        cleaned = cleaned[:-2].strip()

    cleaned = re.sub(r"^(₹|Rs\.?|INR)\s*", "", cleaned).strip()
    cleaned = cleaned.replace(",", "").replace(" ", "")

    if not cleaned:
        return Decimal("0.00")

    try:
        result = Decimal(cleaned)
    except InvalidOperation as e:
        raise ValueError(f"Cannot parse amount: '{amount_str}' (cleaned: '{cleaned}')") from e

    return -result if is_negative else result
