from __future__ import annotations

from decimal import Decimal

import pytest

from core.parsing.amount_parser import parse_indian_amount


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1,00,000.00", Decimal("100000.00")),
        ("1,00,00,000.00", Decimal("10000000.00")),
        ("500.00", Decimal("500.00")),
        ("0.50", Decimal("0.50")),
        ("", Decimal("0.00")),
        ("-", Decimal("0.00")),
        ("—", Decimal("0.00")),
        ("nan", Decimal("0.00")),
        ("₹1,500.00", Decimal("1500.00")),
        ("Rs. 1,500", Decimal("1500.00")),
        ("INR 1500", Decimal("1500.00")),
        ("(1,500.00)", Decimal("-1500.00")),
        ("1,500.00Dr", Decimal("-1500.00")),
        ("1,500.00Cr", Decimal("1500.00")),
        ("-1500", Decimal("-1500")),
        (" 1,500.00 ", Decimal("1500.00")),
    ],
)
def test_parse_amount(raw: str, expected: Decimal) -> None:
    assert parse_indian_amount(raw) == expected


def test_parse_amount_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_indian_amount("abc")


def test_parse_amount_none() -> None:
    assert parse_indian_amount(None) == Decimal("0.00")
