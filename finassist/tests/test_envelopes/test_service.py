from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from core.envelopes.service import (
    compute_envelope_balance,
    manual_envelope_debit,
    split_atm_withdrawal,
)
from db.models import Transaction


async def test_atm_split_creates_envelope_legs_and_flips_parent(
    db, parent_atm_txn_id: int, envelope_ids: dict[str, int], category_lookup: dict[str, int]
):
    splits = [
        {"account_id": envelope_ids["Mom"], "amount": Decimal("5000")},
        {"account_id": envelope_ids["Dad"], "amount": Decimal("4000")},
        {"account_id": envelope_ids["Wife"], "amount": Decimal("3000")},
        {"account_id": envelope_ids["Daughter"], "amount": Decimal("2000")},
    ]

    async with db() as session:
        legs = await split_atm_withdrawal(parent_atm_txn_id, splits, session)
        assert len(legs) == 4

    transfer_cat_id = category_lookup["Inter-account Transfer"]

    async with db() as session:
        parent = await session.get(Transaction, parent_atm_txn_id)
        assert parent is not None
        assert parent.is_transfer == 1
        assert parent.category_id == transfer_cat_id
        assert parent.needs_review == 0
        assert parent.review_reason is None

        rows = (
            await session.execute(
                select(Transaction).where(Transaction.transfer_pair_id == parent_atm_txn_id)
            )
        ).scalars().all()
        assert len(rows) == 4
        for r in rows:
            assert r.type == "credit"
            assert r.is_transfer == 1
            assert r.category_id == transfer_cat_id
            assert r.txn_date == parent.txn_date
            assert "Cash split from" in r.narration


async def test_split_sum_exceeding_parent_raises(
    db, parent_atm_txn_id: int, envelope_ids: dict[str, int]
):
    splits = [
        {"account_id": envelope_ids["Mom"], "amount": Decimal("15000")},
        {"account_id": envelope_ids["Wife"], "amount": Decimal("10000")},
    ]
    async with db() as session:
        with pytest.raises(ValueError):
            await split_atm_withdrawal(parent_atm_txn_id, splits, session)


async def test_split_into_non_envelope_account_raises(
    db, parent_atm_txn_id: int, bank_account_id: int
):
    async with db() as session:
        with pytest.raises(ValueError):
            await split_atm_withdrawal(
                parent_atm_txn_id,
                [{"account_id": bank_account_id, "amount": Decimal("100")}],
                session,
            )


async def test_manual_debit_decrements_balance(
    db, envelope_ids: dict[str, int], parent_atm_txn_id: int, category_lookup: dict[str, int]
):
    mom = envelope_ids["Mom"]

    # Fund Mom's envelope via a split
    async with db() as session:
        await split_atm_withdrawal(
            parent_atm_txn_id,
            [{"account_id": mom, "amount": Decimal("5000")}],
            session,
        )

    async with db() as session:
        bal = await compute_envelope_balance(mom, session)
        assert bal == Decimal("5000")

    # Mom spends 800 on groceries
    async with db() as session:
        await manual_envelope_debit(
            account_id=mom,
            txn_date=date(2026, 4, 16),
            amount=Decimal("800"),
            narration="Groceries at local store",
            category_id=category_lookup["Groceries"],
            session=session,
        )

    async with db() as session:
        bal = await compute_envelope_balance(mom, session)
        assert bal == Decimal("4200")


async def test_compute_balance_with_mixed_credits_and_debits(
    db, envelope_ids: dict[str, int], category_lookup: dict[str, int]
):
    wife = envelope_ids["Wife"]

    async with db() as session:
        # two manual debits
        await manual_envelope_debit(
            account_id=wife,
            txn_date=date(2026, 4, 1),
            amount=Decimal("100"),
            narration="Tea shop",
            category_id=category_lookup["Eating Out"],
            session=session,
        )
        await manual_envelope_debit(
            account_id=wife,
            txn_date=date(2026, 4, 2),
            amount=Decimal("250"),
            narration="Milk",
            category_id=category_lookup["Groceries"],
            session=session,
        )

    # add a synthetic credit (envelope top-up not via split for direct test)
    from db.models import Transaction as Txn
    import hashlib

    async with db() as session:
        top_up = Txn(
            account_id=wife,
            txn_date=date(2026, 4, 5),
            amount=Decimal("1000"),
            type="credit",
            narration="manual top-up",
            narration_hash=hashlib.sha256(b"manual top-up").hexdigest(),
            is_transfer=1,
            category_id=category_lookup["Inter-account Transfer"],
        )
        session.add(top_up)
        await session.commit()

    async with db() as session:
        bal = await compute_envelope_balance(wife, session)
        # 0 opening + 1000 credit - (100 + 250) debits = 650
        assert bal == Decimal("650")
