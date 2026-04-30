from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from db.init import initialize
from db.models import Account, Category, Transaction
from db.session import make_engine, make_session_factory


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "finassist.db"
    await initialize(db_path)
    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    yield factory
    await engine.dispose()


@pytest.fixture
async def bank_account_id(db) -> int:
    async with db() as session:
        a = Account(name="HDFC", type="bank", bank_code="HDFC", currency="INR", is_active=1)
        session.add(a)
        await session.commit()
        await session.refresh(a)
        return a.id


@pytest.fixture
async def envelope_ids(db) -> dict[str, int]:
    owners = ["Mom", "Dad", "Wife", "Daughter"]
    ids: dict[str, int] = {}
    async with db() as session:
        for owner in owners:
            a = Account(
                name=f"Cash:{owner}",
                type="cash_envelope",
                envelope_owner=owner,
                currency="INR",
                is_active=1,
                opening_balance=Decimal("0"),
            )
            session.add(a)
            await session.flush()
            ids[owner] = a.id
        await session.commit()
    return ids


@pytest.fixture
async def category_lookup(db) -> dict[str, int]:
    async with db() as session:
        rows = (await session.execute(select(Category))).scalars().all()
    return {c.name: c.id for c in rows}


@pytest.fixture
async def parent_atm_txn_id(db, bank_account_id: int) -> int:
    """Create an unclassified ATM withdrawal debit on the bank account."""
    async with db() as session:
        narration = "ATW/CASH WDL/HDFC ATM CHENNAI/123456"
        narration_hash = hashlib.sha256(narration.lower().encode("utf-8")).hexdigest()
        t = Transaction(
            account_id=bank_account_id,
            txn_date=date(2026, 4, 15),
            amount=Decimal("20000"),
            type="debit",
            narration=narration,
            narration_hash=narration_hash,
            is_transfer=0,
            needs_review=1,
            review_reason="classification",
            classification_source="unclassified",
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return t.id
