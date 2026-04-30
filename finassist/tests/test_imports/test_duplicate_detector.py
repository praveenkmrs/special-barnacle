from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from core.imports.duplicate_detector import DupVerdict, check_duplicate
from core.imports.service import import_statement
from core.parsing.raw_transaction import RawTransaction
from db.models import Transaction


def _hdfc_csv(tmp_path: Path, rows: list[list[str]]) -> Path:
    p = tmp_path / "hdfc.csv"
    header = [
        "Date",
        "Narration",
        "Chq./Ref.No.",
        "Value Dt",
        "Withdrawal Amt.",
        "Deposit Amt.",
        "Closing Balance",
    ]
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows([header] + rows)
    return p


async def test_clean_first_import(hdfc_account, initialized_db, tmp_path):
    _e, factory, _ = initialized_db
    csv_path = _hdfc_csv(
        tmp_path,
        [
            ["01/01/24", "UPI-FOO-ICIC0001-1-", "REF1", "01/01/24", "100", "", "9,900"],
        ],
    )
    async with factory() as session:
        result = await import_statement(csv_path, hdfc_account, session)
    assert result.rows_imported == 1
    assert result.rows_duplicate == 0
    assert result.rows_ambiguous == 0


async def test_definite_duplicate_skipped_silently(hdfc_account, initialized_db, tmp_path):
    """Re-importing the same statement should silently skip every row."""
    _e, factory, _ = initialized_db
    csv_path = _hdfc_csv(
        tmp_path,
        [
            ["01/01/24", "UPI-FOO-ICIC0001-1-", "REF1", "01/01/24", "100", "", "9,900"],
            ["02/01/24", "UPI-BAR-ICIC0001-2-", "REF2", "02/01/24", "200", "", "9,700"],
        ],
    )
    async with factory() as session:
        first = await import_statement(csv_path, hdfc_account, session)
    assert first.rows_imported == 2

    async with factory() as session:
        second = await import_statement(csv_path, hdfc_account, session)
    assert second.rows_imported == 0
    assert second.rows_duplicate == 2
    assert second.rows_ambiguous == 0

    async with factory() as session:
        count = (
            await session.execute(select(Transaction).where(Transaction.account_id == hdfc_account))
        ).scalars().all()
    assert len(count) == 2  # No new rows created


async def test_two_legitimate_same_day_coffees_no_refs_no_balances(
    hdfc_account, initialized_db, tmp_path
):
    """Both rows have null reference AND null balance → ambiguous, both flagged."""
    _e, factory, _ = initialized_db
    # Reference and balance are blank → null in DB
    csv_path = _hdfc_csv(
        tmp_path,
        [
            ["01/01/24", "UPI-COFFEE", "", "01/01/24", "100", "", ""],
            ["01/01/24", "UPI-COFFEE", "", "01/01/24", "100", "", ""],
        ],
    )
    async with factory() as session:
        result = await import_statement(csv_path, hdfc_account, session)

    assert result.rows_imported == 2
    assert result.rows_ambiguous >= 1  # second insertion was ambiguous

    async with factory() as session:
        rows = (
            await session.execute(
                select(Transaction).where(Transaction.account_id == hdfc_account)
            )
        ).scalars().all()
    assert len(rows) == 2
    assert all(r.dup_group_id is not None for r in rows)
    assert all(r.needs_review == 1 for r in rows)
    assert all(r.review_reason == "duplicate" for r in rows)
    # Both share the same group id
    assert rows[0].dup_group_id == rows[1].dup_group_id


async def test_two_real_coffees_distinct_balances_clean(
    hdfc_account, initialized_db, tmp_path
):
    """Same merchant + day + amount but different balances → clean (Tier B)."""
    _e, factory, _ = initialized_db
    csv_path = _hdfc_csv(
        tmp_path,
        [
            ["01/01/24", "UPI-COFFEE", "", "01/01/24", "100", "", "9,900"],
            ["01/01/24", "UPI-COFFEE", "", "01/01/24", "100", "", "9,800"],
        ],
    )
    async with factory() as session:
        result = await import_statement(csv_path, hdfc_account, session)

    assert result.rows_imported == 2
    assert result.rows_ambiguous == 0
    assert result.rows_duplicate == 0

    async with factory() as session:
        rows = (
            await session.execute(
                select(Transaction).where(Transaction.account_id == hdfc_account)
            )
        ).scalars().all()
    assert all(r.dup_group_id is None for r in rows)
    # Not flagged as duplicates — but classifier runs after import so they may be
    # flagged for classification review. The dup verdict is what we're testing here.
    assert all(r.review_reason != "duplicate" for r in rows)


async def test_check_duplicate_returns_clean_when_no_match(initialized_db, hdfc_account):
    _e, factory, _ = initialized_db
    incoming = RawTransaction(
        txn_date=date(2024, 1, 1),
        amount=Decimal("100"),
        type="debit",
        narration="UPI-X",
        balance_after=None,
        account_id=hdfc_account,
        reference=None,
    )
    incoming.compute_hash()
    async with factory() as session:
        result = await check_duplicate(incoming, hdfc_account, session)
    assert result.verdict is DupVerdict.CLEAN
