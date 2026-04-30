from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from core.transfers.pair_matcher import (
    confirm_pair,
    find_pair_candidates,
    reject_pair,
    stage_pairs_for_review,
)
from db.models import Transaction


async def _add_txn(
    session,
    *,
    account_id: int,
    txn_date: date,
    amount: Decimal,
    type_: str,
    narration: str = "TRANSFER",
    is_transfer: int = 0,
    transfer_pair_id: int | None = None,
) -> int:
    t = Transaction(
        account_id=account_id,
        txn_date=txn_date,
        amount=amount,
        type=type_,
        narration=narration,
        narration_hash=narration + str(txn_date),
        is_transfer=is_transfer,
        transfer_pair_id=transfer_pair_id,
    )
    session.add(t)
    await session.commit()
    await session.refresh(t)
    return t.id


@pytest.mark.asyncio
async def test_finds_pair_within_72h(db, account_id, account_id_b):
    async with db() as session:
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 2),
            amount=Decimal("5000"),
            type_="credit",
        )
        pairs = await find_pair_candidates(session)
    assert len(pairs) == 1
    debit, credit = pairs[0]
    assert debit.type == "debit"
    assert credit.type == "credit"
    assert debit.account_id != credit.account_id


@pytest.mark.asyncio
async def test_no_pair_when_dates_too_far(db, account_id, account_id_b):
    async with db() as session:
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 6),
            amount=Decimal("5000"),
            type_="credit",
        )
        pairs = await find_pair_candidates(session)
    assert pairs == []


@pytest.mark.asyncio
async def test_no_pair_when_amounts_differ(db, account_id, account_id_b):
    async with db() as session:
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 2),
            amount=Decimal("4999"),
            type_="credit",
        )
        pairs = await find_pair_candidates(session)
    assert pairs == []


@pytest.mark.asyncio
async def test_no_pair_within_same_account(db, account_id):
    async with db() as session:
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 2),
            amount=Decimal("5000"),
            type_="credit",
        )
        pairs = await find_pair_candidates(session)
    assert pairs == []


@pytest.mark.asyncio
async def test_already_confirmed_transfer_not_restaged(db, account_id, account_id_b):
    async with db() as session:
        d_id = await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
            is_transfer=1,
        )
        await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 2),
            amount=Decimal("5000"),
            type_="credit",
            is_transfer=1,
            transfer_pair_id=d_id,
        )
        pairs = await find_pair_candidates(session)
    assert pairs == []


@pytest.mark.asyncio
async def test_stage_then_confirm(db, account_id, account_id_b, category_lookup):
    async with db() as session:
        d_id = await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        c_id = await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 2),
            amount=Decimal("5000"),
            type_="credit",
        )
        staged = await stage_pairs_for_review(session)
        assert staged == 1

    async with db() as session:
        d = (await session.execute(select(Transaction).where(Transaction.id == d_id))).scalar_one()
        c = (await session.execute(select(Transaction).where(Transaction.id == c_id))).scalar_one()
        assert d.needs_review == 1 and d.review_reason == "transfer"
        assert c.needs_review == 1 and c.review_reason == "transfer"
        assert d.transfer_pair_id == c_id
        assert c.transfer_pair_id == d_id

    async with db() as session:
        await confirm_pair(d_id, c_id, session)

    async with db() as session:
        d = (await session.execute(select(Transaction).where(Transaction.id == d_id))).scalar_one()
        c = (await session.execute(select(Transaction).where(Transaction.id == c_id))).scalar_one()
        assert d.is_transfer == 1 and c.is_transfer == 1
        assert d.needs_review == 0 and c.needs_review == 0
        assert d.review_reason is None and c.review_reason is None
        assert d.category_id == category_lookup["Inter-account Transfer"]
        assert c.category_id == category_lookup["Inter-account Transfer"]
        assert d.transfer_pair_id == c_id
        assert c.transfer_pair_id == d_id


@pytest.mark.asyncio
async def test_reject_pair_clears_link(db, account_id, account_id_b):
    async with db() as session:
        d_id = await _add_txn(
            session,
            account_id=account_id,
            txn_date=date(2024, 1, 1),
            amount=Decimal("5000"),
            type_="debit",
        )
        c_id = await _add_txn(
            session,
            account_id=account_id_b,
            txn_date=date(2024, 1, 2),
            amount=Decimal("5000"),
            type_="credit",
        )
        await stage_pairs_for_review(session)

    async with db() as session:
        await reject_pair(d_id, c_id, session)

    async with db() as session:
        d = (await session.execute(select(Transaction).where(Transaction.id == d_id))).scalar_one()
        c = (await session.execute(select(Transaction).where(Transaction.id == c_id))).scalar_one()
        assert d.is_transfer == 0 and c.is_transfer == 0
        assert d.transfer_pair_id is None and c.transfer_pair_id is None
        assert d.needs_review == 0 and c.needs_review == 0
        assert d.review_reason is None and c.review_reason is None
