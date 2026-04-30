from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.banks.hdfc.adapter import HDFCAdapter


def test_csv_end_to_end(hdfc_csv_simple) -> None:
    adapter = HDFCAdapter()
    txns = adapter.parse(hdfc_csv_simple, account_id=1)
    assert len(txns) == 4
    assert txns[0].txn_date == date(2024, 1, 1)
    assert txns[0].type == "debit"
    assert txns[0].amount == Decimal("500.00")
    assert txns[1].type == "credit"
    assert txns[1].amount == Decimal("50000.00")
    assert all(t.bank_code == "HDFC" for t in txns)
    assert all(t.narration_hash for t in txns)


def test_csv_detect_passes(hdfc_csv_simple) -> None:
    adapter = HDFCAdapter()
    assert adapter.detect(hdfc_csv_simple) is True


def test_csv_detect_fails_for_unknown(tmp_path) -> None:
    p = tmp_path / "unknown.csv"
    p.write_text("alpha,beta,gamma\n1,2,3\n")
    adapter = HDFCAdapter()
    assert adapter.detect(p) is False


def test_statement_period(hdfc_csv_simple) -> None:
    adapter = HDFCAdapter()
    start, end = adapter.statement_period(hdfc_csv_simple)
    assert start == date(2024, 1, 1)
    assert end == date(2024, 1, 5)
