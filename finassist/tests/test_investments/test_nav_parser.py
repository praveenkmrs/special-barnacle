from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.investments.nav_fetcher import parse_amfi_navall


SAMPLE = """\
Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date

Open Ended Schemes(Equity Scheme - Large Cap Fund)

Aditya Birla Sun Life Mutual Fund

119551;INF209KA12Z1;INF209KA13Z9;Aditya Birla Sun Life Frontline Equity Fund - Growth;456.7890;25-Apr-2026
119552;INF209KA14Z7;;Aditya Birla Sun Life Frontline Equity Fund - Dividend;45.6789;25-Apr-2026

Open Ended Schemes(Debt Scheme)

100123;INF999XX01Z1;;Some Debt Fund Growth;12.3456;25-Apr-2026
"""


def test_parse_basic():
    rows = parse_amfi_navall(SAMPLE)
    assert len(rows) == 3
    r = rows[0]
    assert r["scheme_code"] == "119551"
    assert r["nav"] == Decimal("456.7890")
    assert r["nav_date"] == date(2026, 4, 25)
    assert "Frontline" in r["scheme_name"]


def test_skips_section_markers_and_blanks():
    rows = parse_amfi_navall(SAMPLE)
    codes = [r["scheme_code"] for r in rows]
    assert "Scheme Code" not in codes
    # No header tokens or section names should sneak in
    assert all(c[0].isdigit() for c in codes)


def test_bad_rows_skipped_not_raised():
    bad = """\
123456;ISINX;ISINY;Fund X;NOT_A_NUMBER;25-Apr-2026
123457;ISINX;ISINY;Fund Y;10.50;NOT-A-DATE
123458;ISINX;ISINY;Fund Z
123459;ISINX;ISINY;Fund OK;10.5;25-Apr-2026
"""
    rows = parse_amfi_navall(bad)
    assert len(rows) == 1
    assert rows[0]["scheme_code"] == "123459"


def test_empty_input():
    assert parse_amfi_navall("") == []
    assert parse_amfi_navall("\n\n\n") == []
