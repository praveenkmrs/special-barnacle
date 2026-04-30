from __future__ import annotations

from pathlib import Path

import pytest

from db.init import initialize
from db.session import make_engine, make_session_factory


@pytest.fixture
async def db(tmp_path: Path):
    db_path = tmp_path / "finassist.db"
    await initialize(db_path)
    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    yield factory
    await engine.dispose()
