from __future__ import annotations

from datetime import date

from core.parsing.date_parser import looks_like_date, parse_date


def test_hdfc_short_year() -> None:
    assert parse_date("22/06/17", "%d/%m/%y") == date(2017, 6, 22)


def test_hdfc_full_year() -> None:
    assert parse_date("22/06/2017", "%d/%m/%y", "%d/%m/%Y") == date(2017, 6, 22)


def test_axis_format() -> None:
    assert parse_date("15-06-2024") == date(2024, 6, 15)


def test_iso_format() -> None:
    assert parse_date("2024-06-15") == date(2024, 6, 15)


def test_empty_returns_none() -> None:
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("nan") is None


def test_dayfirst_ambiguous() -> None:
    # Indian convention: 1-Feb, never Feb-1
    assert parse_date("01/02/24", "%d/%m/%y") == date(2024, 2, 1)


def test_invalid_returns_none() -> None:
    assert parse_date("not a date") is None


def test_looks_like_date() -> None:
    assert looks_like_date("22/06/17") is True
    assert looks_like_date("1-12-2024") is True
    assert looks_like_date("IMPS TRANSFER") is False
    assert looks_like_date("") is False
    assert looks_like_date("nan") is False
