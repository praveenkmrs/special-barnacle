from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from core.investments.holdings_service import (
    InvestmentError,
    buy_units,
    link_sip_transaction,
)
from core.investments.valuation import fd_interest
from db.models import Account, Holding, HoldingTransaction, NavCache, Transaction


async def _seed_account_and_holding(session) -> tuple[int, int]:
    acct = Account(name="MF Broker", type="mf", currency="INR", is_active=1)
    session.add(acct)
    await session.commit()
    await session.refresh(acct)

    h = Holding(
        account_id=acct.id,
        instrument_type="mf",
        identifier="119551",
        name="Test Fund",
        units=Decimal("0"),
        total_invested=Decimal("0"),
    )
    session.add(h)
    await session.commit()
    await session.refresh(h)
    return acct.id, h.id


async def _seed_nav(session, scheme: str, on_date: date, nav: str) -> None:
    session.add(
        NavCache(
            scheme_code=scheme,
            scheme_name="Test Fund",
            nav=Decimal(nav),
            nav_date=on_date,
        )
    )
    await session.commit()


async def test_buy_units_with_exact_nav(db):
    async with db() as session:
        _, holding_id = await _seed_account_and_holding(session)
        await _seed_nav(session, "119551", date(2026, 4, 1), "100.00")

        ht = await buy_units(
            holding_id=holding_id,
            txn_date=date(2026, 4, 1),
            amount=Decimal("10000"),
            linked_transaction_id=None,
            session=session,
        )
        assert ht.type == "buy"
        assert Decimal(ht.units) == Decimal("100")

        h = await session.get(Holding, holding_id)
        assert Decimal(h.units) == Decimal("100")
        assert Decimal(h.total_invested) == Decimal("10000")
        assert Decimal(h.avg_cost) == Decimal("100")


async def test_buy_units_falls_back_to_prior_nav(db):
    async with db() as session:
        _, holding_id = await _seed_account_and_holding(session)
        # NAV is from 3 days ago; txn date has no exact match.
        await _seed_nav(session, "119551", date(2026, 4, 1), "50.00")

        ht = await buy_units(
            holding_id=holding_id,
            txn_date=date(2026, 4, 5),
            amount=Decimal("5000"),
            linked_transaction_id=None,
            session=session,
        )
        assert Decimal(ht.units) == Decimal("100")
        assert Decimal(ht.price_per_unit) == Decimal("50.00")


async def test_buy_units_raises_when_no_nav(db):
    async with db() as session:
        _, holding_id = await _seed_account_and_holding(session)
        with pytest.raises(InvestmentError):
            await buy_units(
                holding_id=holding_id,
                txn_date=date(2026, 4, 5),
                amount=Decimal("5000"),
                linked_transaction_id=None,
                session=session,
            )


async def test_link_sip_transaction(db):
    async with db() as session:
        acct_id, holding_id = await _seed_account_and_holding(session)
        await _seed_nav(session, "119551", date(2026, 4, 5), "200.00")

        txn = Transaction(
            account_id=acct_id,
            txn_date=date(2026, 4, 5),
            amount=Decimal("10000"),
            type="debit",
            narration="ACH D- HDFC AMC- SIP",
            narration_hash="abc123",
        )
        session.add(txn)
        await session.commit()
        await session.refresh(txn)

        ht = await link_sip_transaction(txn.id, holding_id, session)
        assert ht.linked_transaction_id == txn.id
        assert Decimal(ht.units) == Decimal("50")

        h = await session.get(Holding, holding_id)
        assert Decimal(h.units) == Decimal("50")
        assert Decimal(h.total_invested) == Decimal("10000")

        # The holding_transactions table should reflect the buy.
        rows = (
            await session.execute(
                select(HoldingTransaction).where(
                    HoldingTransaction.holding_id == holding_id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].type == "buy"


def test_fd_interest_simple():
    # 100,000 @ 7% for 1 year (365 days) = 7000
    interest = fd_interest(
        Decimal("100000"),
        Decimal("7"),
        date(2025, 4, 1),
        date(2026, 4, 1),
    )
    assert interest == Decimal("7000")


def test_fd_interest_zero_for_future_start():
    interest = fd_interest(
        Decimal("100000"),
        Decimal("7"),
        date(2026, 4, 1),
        date(2025, 4, 1),
    )
    assert interest == Decimal("0")


def test_fd_interest_partial_year():
    # 100,000 @ 10% for 73 days (1/5 year) = 2000
    interest = fd_interest(
        Decimal("100000"),
        Decimal("10"),
        date(2026, 1, 1),
        date(2026, 3, 15),  # 73 days later
    )
    assert interest == Decimal("100000") * Decimal("10") / Decimal("100") * (
        Decimal(73) / Decimal(365)
    )
