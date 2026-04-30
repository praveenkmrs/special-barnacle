from __future__ import annotations

import hashlib
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from core.subscriptions.detector import detect_subscriptions
from core.subscriptions.linker import link_recent_to_subscriptions, project_next_n
from db.models import Subscription, Transaction


def _hash(narration: str) -> str:
    return hashlib.sha256(narration.encode("utf-8")).hexdigest()


async def _add_txn(
    session,
    *,
    account_id: int,
    txn_date: date,
    amount: str,
    narration: str = "NETFLIX SUBSCRIPTION",
    type_: str = "debit",
) -> Transaction:
    t = Transaction(
        account_id=account_id,
        txn_date=txn_date,
        amount=Decimal(amount),
        type=type_,
        narration=narration,
        narration_hash=_hash(narration),
        classification_source="unclassified",
    )
    session.add(t)
    await session.flush()
    return t


async def test_three_monthly_netflix_detected_as_monthly(db, account_id):
    today = date.today()
    async with db() as session:
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=60), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=30), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=0), amount="649")
        await session.commit()

    async with db() as session:
        subs = await detect_subscriptions(session)
        await session.commit()
        assert len(subs) == 1
        s = subs[0]
        assert s.cadence == "monthly"
        assert s.auto_detected == 1
        assert Decimal(str(s.expected_amount)) == Decimal("649")
        assert s.next_expected_date == today + timedelta(days=30)


async def test_amounts_varying_more_than_5pct_not_detected(db, account_id):
    today = date.today()
    async with db() as session:
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=60), amount="100")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=30), amount="200")
        await session.commit()

    async with db() as session:
        subs = await detect_subscriptions(session)
        await session.commit()
        assert len(subs) == 0


async def test_detection_idempotent(db, account_id):
    today = date.today()
    async with db() as session:
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=60), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=30), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today, amount="649")
        await session.commit()

    async with db() as session:
        await detect_subscriptions(session)
        await session.commit()
    async with db() as session:
        await detect_subscriptions(session)
        await session.commit()

    async with db() as session:
        rows = (await session.execute(select(Subscription))).scalars().all()
        assert len(rows) == 1


async def test_past_transactions_get_linked(db, account_id):
    today = date.today()
    async with db() as session:
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=60), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=30), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today, amount="649")
        await session.commit()

    async with db() as session:
        await detect_subscriptions(session)
        await session.commit()

    async with db() as session:
        rows = (await session.execute(select(Transaction))).scalars().all()
        assert len(rows) == 3
        assert all(t.subscription_id is not None for t in rows)


async def test_linker_attaches_new_unlinked_txn(db, account_id):
    today = date.today()
    async with db() as session:
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=60), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today - timedelta(days=30), amount="649")
        await _add_txn(session, account_id=account_id, txn_date=today, amount="649")
        await session.commit()

    async with db() as session:
        await detect_subscriptions(session)
        await session.commit()

    # Add a new unlinked txn matching signature
    async with db() as session:
        await _add_txn(
            session,
            account_id=account_id,
            txn_date=today + timedelta(days=30),
            amount="649",
        )
        await session.commit()

    async with db() as session:
        n = await link_recent_to_subscriptions(session)
        await session.commit()
        assert n == 1


async def test_project_next_n_monthly():
    sub = Subscription(
        name="X",
        cadence="monthly",
        next_expected_date=date(2026, 5, 1),
        status="active",
    )
    out = project_next_n(sub, n=3)
    assert len(out) == 3
    assert out[0] == date(2026, 5, 1)
    assert (out[1] - out[0]).days == 30
