from __future__ import annotations

import re

from core.classifier.pattern_extractor import extract_patterns


def test_upi_merchant_token() -> None:
    pats = extract_patterns("UPI-SWIGGY-YESB0001-1234-")
    assert any(p.pattern_type == "token" for p in pats)


def test_vpa_pattern() -> None:
    pats = extract_patterns("UPI-johndoe@okicici-1234-PAY")
    assert any(p.pattern_type == "vpa" for p in pats)


def test_prefix_pattern_always_present() -> None:
    pats = extract_patterns("ATW-XXXXXX1234-NS BLR")
    assert any(p.pattern_type == "prefix" for p in pats)


def test_empty_returns_empty_list() -> None:
    assert extract_patterns("") == []
    assert extract_patterns("   ") == []


def test_token_pattern_matches_similar_narration() -> None:
    pats = extract_patterns("UPI-NETFLIX-OKAXIS-1-")
    token_pats = [p for p in pats if p.pattern_type == "token"]
    # Token pattern from NETFLIX should match a future Netflix txn
    assert any(re.search(p.pattern, "UPI-NETFLIX-PAYMENT-2-", re.IGNORECASE) for p in token_pats)
