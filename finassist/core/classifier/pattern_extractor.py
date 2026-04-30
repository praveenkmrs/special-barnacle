from __future__ import annotations

import re
from dataclasses import dataclass

# Words to ignore when picking a "top token" — common in payroll/bank narrations
_STOPWORDS = {
    "upi",
    "imps",
    "neft",
    "rtgs",
    "ach",
    "txn",
    "payment",
    "txnref",
    "ref",
    "sal",
    "to",
    "from",
    "for",
    "the",
    "and",
    "of",
    "by",
    "on",
}


@dataclass(frozen=True)
class Pattern:
    pattern: str
    pattern_type: str  # narration | vpa | prefix | token | exact


def extract_patterns(narration: str) -> list[Pattern]:
    """Generate candidate regex patterns from a narration at multiple granularities.

    Returns most-specific first so the import service can pick the longest unique one.
    """
    if not narration:
        return []

    n = narration.strip()
    patterns: list[Pattern] = []

    # 1. VPA pattern (most specific — exact handle)
    vpa_match = re.search(r"([A-Za-z0-9._-]+@[a-zA-Z0-9]+)", n)
    if vpa_match:
        vpa = vpa_match.group(1)
        # *@handle form for portability
        handle = vpa.split("@", 1)[1]
        patterns.append(Pattern(pattern=rf".*@{re.escape(handle)}.*", pattern_type="vpa"))

    # 2. UPI/IMPS merchant token: parse hyphen-delimited and pick second segment
    upper = n.upper()
    method_prefixes = ("UPI-", "IMPS-", "NEFT-", "RTGS-", "ACH D-", "ACH C-")
    for prefix in method_prefixes:
        if upper.startswith(prefix):
            parts = [p.strip() for p in n.split("-") if p.strip()]
            if len(parts) >= 2:
                merchant = parts[1]
                if not merchant.startswith("X") and len(merchant) > 2:
                    patterns.append(
                        Pattern(
                            pattern=rf"^{re.escape(prefix.rstrip('-'))}.*{re.escape(merchant)}.*",
                            pattern_type="token",
                        )
                    )
            break

    # 3. Prefix (first 20 chars, escaped)
    prefix_text = n[:20]
    if prefix_text:
        patterns.append(
            Pattern(pattern=f"^{re.escape(prefix_text)}.*", pattern_type="prefix")
        )

    # 4. Top non-stopword token (>= 4 chars)
    tokens = re.findall(r"[A-Za-z]{4,}", n)
    candidates = [t for t in tokens if t.lower() not in _STOPWORDS]
    if candidates:
        # pick longest (proxy for highest IDF without having corpus stats yet)
        top = max(candidates, key=len)
        patterns.append(
            Pattern(pattern=rf".*\b{re.escape(top)}\b.*", pattern_type="token")
        )

    # Dedup while preserving order
    seen: set[tuple[str, str]] = set()
    unique: list[Pattern] = []
    for p in patterns:
        key = (p.pattern, p.pattern_type)
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique
