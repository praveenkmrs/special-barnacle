from __future__ import annotations

from datetime import date
from decimal import Decimal

from core.parsing.balance_validator import validate_running_balance
from core.parsing.raw_transaction import RawTransaction


def _txn(amount: str, type_: str, balance: str | None) -> RawTransaction:
    t = RawTransaction(
        txn_date=date(2024, 1, 1),
        amount=Decimal(amount),
        type=type_,  # type: ignore[arg-type]
        narration="x",
        balance_after=Decimal(balance) if balance else None,
        account_id=1,
    )
    t.compute_hash()
    return t


def test_valid_chain_no_discrepancies() -> None:
    txns = [
        _txn("500", "debit", "9500"),
        _txn("1000", "credit", "10500"),
    ]
    assert validate_running_balance(txns, opening_balance=Decimal("10000")) == []


def test_one_off_balance_flagged() -> None:
    txns = [
        _txn("500", "debit", "9500"),
        _txn("1000", "credit", "11000"),  # should be 10500
    ]
    discrepancies = validate_running_balance(txns, opening_balance=Decimal("10000"))
    assert len(discrepancies) == 1
    assert discrepancies[0]["index"] == 1


def test_chain_break_on_null_balance() -> None:
    txns = [
        _txn("500", "debit", None),
        _txn("1000", "credit", "10500"),
    ]
    # Chain breaks → no discrepancy from #1 even though we can't verify
    assert validate_running_balance(txns, opening_balance=Decimal("10000")) == []


def test_tolerance_applied() -> None:
    txns = [_txn("500", "debit", "9500.01")]
    # Within 0.02 paisa tolerance
    assert validate_running_balance(txns, opening_balance=Decimal("10000")) == []
