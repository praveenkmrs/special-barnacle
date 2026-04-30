from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from db.init import initialize
from db.models import Account, Category
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
async def category_lookup(db) -> dict[str, int]:
    async with db() as session:
        rows = (await session.execute(select(Category))).scalars().all()
    return {c.name: c.id for c in rows}


@pytest.fixture
async def bank_account_id(db) -> int:
    async with db() as session:
        a = Account(
            name="HDFC Salary",
            type="bank",
            bank_code="HDFC",
            currency="INR",
            is_active=1,
            opening_balance="10000",
        )
        session.add(a)
        await session.commit()
        await session.refresh(a)
        return a.id


@pytest.fixture
async def envelope_account_id(db) -> int:
    async with db() as session:
        a = Account(
            name="Cash:Mom",
            type="cash_envelope",
            envelope_owner="Mom",
            currency="INR",
            is_active=1,
            opening_balance="0",
        )
        session.add(a)
        await session.commit()
        await session.refresh(a)
        return a.id
