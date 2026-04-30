from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.init import initialize
from db.models import Category
from db.session import make_engine, make_session_factory


async def _count_categories(db_path: Path) -> tuple[int, int]:
    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            cats = (await session.execute(select(Category))).scalars().all()
            top = sum(1 for c in cats if c.parent_id is None)
            return len(cats), top
    finally:
        await engine.dispose()


async def test_initialize_creates_schema_and_seeds(tmp_path):
    db_path = tmp_path / "finassist.db"
    inserted = await initialize(db_path)
    assert inserted > 0

    total, top_level = await _count_categories(db_path)
    assert top_level == 12  # Income..Uncategorized
    assert total > 50

    # Idempotency check
    inserted_again = await initialize(db_path)
    assert inserted_again == 0


async def test_transfer_and_income_flags(tmp_path):
    db_path = tmp_path / "finassist.db"
    await initialize(db_path)

    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            session: AsyncSession
            transfers = (
                await session.execute(
                    select(Category).where(Category.is_transfer == 1)
                )
            ).scalars().all()
            income = (
                await session.execute(
                    select(Category).where(Category.is_income == 1)
                )
            ).scalars().all()

            assert any(c.name == "Transfers" and c.parent_id is None for c in transfers)
            assert all(c.is_transfer == 1 for c in transfers)

            income_top = [c for c in income if c.parent_id is None]
            assert len(income_top) == 1 and income_top[0].name == "Income"
    finally:
        await engine.dispose()
