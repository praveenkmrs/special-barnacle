from __future__ import annotations

from datetime import date
from decimal import Decimal

from db.models import Transaction
from core.analytics.balances import cash_buffer, per_account_balances
from core.analytics.aggregations import category_breakdown, net_cashflow


async def _add_txn(
    session,
    *,
    account_id: int,
    type_: str,
    amount: str,
    txn_date: date,
    category_id: int | None = None,
    is_transfer: int = 0,
) -> None:
    session.add(
        Transaction(
            account_id=account_id,
            txn_date=txn_date,
            amount=Decimal(amount),
            type=type_,
            narration=f"test {amount}",
            narration_hash=f"h{amount}{type_}{txn_date}",
            category_id=category_id,
            is_transfer=is_transfer,
            classification_source="manual" if category_id else "unclassified",
        )
    )


async def test_per_account_balances_includes_opening_and_txns(
    db, bank_account_id, envelope_account_id, category_lookup
):
    food = category_lookup["Groceries"]
    async with db() as session:
        await _add_txn(
            session, account_id=bank_account_id, type_="debit",
            amount="500", txn_date=date(2024, 1, 1), category_id=food,
        )
        await _add_txn(
            session, account_id=bank_account_id, type_="credit",
            amount="50000", txn_date=date(2024, 1, 5), category_id=category_lookup["Salary"],
        )
        await _add_txn(
            session, account_id=envelope_account_id, type_="credit",
            amount="2000", txn_date=date(2024, 1, 2),
            category_id=category_lookup["Inter-account Transfer"], is_transfer=1,
        )
        await session.commit()

    async with db() as session:
        balances = await per_account_balances(session)
        bank = next(b for b in balances if b.account_id == bank_account_id)
        env = next(b for b in balances if b.account_id == envelope_account_id)
        # opening 10000 + 50000 - 500 = 59500
        assert bank.balance == Decimal("59500")
        # opening 0 + 2000 = 2000
        assert env.balance == Decimal("2000")


async def test_cash_buffer_sums_bank_and_envelope(
    db, bank_account_id, envelope_account_id, category_lookup
):
    async with db() as session:
        await _add_txn(
            session, account_id=bank_account_id, type_="credit",
            amount="1000", txn_date=date(2024, 1, 1),
        )
        await _add_txn(
            session, account_id=envelope_account_id, type_="credit",
            amount="500", txn_date=date(2024, 1, 1),
        )
        await session.commit()

    async with db() as session:
        cb = await cash_buffer(session)
        # 10000 (bank opening) + 1000 + 0 (envelope opening) + 500 = 11500
        assert cb == Decimal("11500")


async def test_category_breakdown_excludes_transfers(
    db, bank_account_id, envelope_account_id, category_lookup
):
    food = category_lookup["Groceries"]
    transfer = category_lookup["Inter-account Transfer"]
    async with db() as session:
        await _add_txn(
            session, account_id=bank_account_id, type_="debit",
            amount="800", txn_date=date(2024, 1, 10), category_id=food,
        )
        await _add_txn(
            session, account_id=bank_account_id, type_="debit",
            amount="5000", txn_date=date(2024, 1, 11),
            category_id=transfer, is_transfer=1,
        )
        await session.commit()

    async with db() as session:
        rows = await category_breakdown(
            session, from_date=date(2024, 1, 1), to_date=date(2024, 1, 31)
        )
        cat_names = {r.category_name for r in rows}
        assert "Groceries" in cat_names
        assert "Inter-account Transfer" not in cat_names


async def test_net_cashflow_excludes_transfers(
    db, bank_account_id, category_lookup
):
    salary = category_lookup["Salary"]
    food = category_lookup["Groceries"]
    transfer = category_lookup["Inter-account Transfer"]
    async with db() as session:
        await _add_txn(
            session, account_id=bank_account_id, type_="credit",
            amount="50000", txn_date=date(2024, 1, 1), category_id=salary,
        )
        await _add_txn(
            session, account_id=bank_account_id, type_="debit",
            amount="2000", txn_date=date(2024, 1, 2), category_id=food,
        )
        await _add_txn(
            session, account_id=bank_account_id, type_="debit",
            amount="10000", txn_date=date(2024, 1, 3),
            category_id=transfer, is_transfer=1,
        )
        await session.commit()

    async with db() as session:
        income, expenses, net = await net_cashflow(
            session, from_date=date(2024, 1, 1), to_date=date(2024, 1, 31)
        )
        assert income == Decimal("50000")
        assert expenses == Decimal("2000")
        assert net == Decimal("48000")
