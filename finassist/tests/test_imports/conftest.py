from __future__ import annotations

from pathlib import Path

import pytest

from db.init import initialize
from db.models import Account
from db.session import make_engine, make_session_factory


@pytest.fixture
async def initialized_db(tmp_path: Path):
    db_path = tmp_path / "finassist.db"
    await initialize(db_path)
    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    yield (engine, factory, db_path)
    await engine.dispose()


@pytest.fixture
async def hdfc_account(initialized_db):
    _engine, factory, _db = initialized_db
    async with factory() as session:
        acct = Account(
            name="HDFC Salary",
            type="bank",
            bank_code="HDFC",
            account_number_masked="XXXXXX1234",
            currency="INR",
            is_active=1,
        )
        session.add(acct)
        await session.commit()
        await session.refresh(acct)
        return acct.id
