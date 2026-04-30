from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from db.types import DecimalText


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield eng
    await eng.dispose()


@pytest.fixture
async def amounts_table(engine):
    metadata = MetaData()
    table = Table(
        "amounts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", DecimalText, nullable=False),
    )
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    return table


async def _roundtrip(engine, amounts_table, raw):
    async with AsyncSession(engine) as session:
        await session.execute(insert(amounts_table).values(value=raw))
        await session.commit()
        result = await session.execute(
            select(amounts_table.c.value).order_by(amounts_table.c.id.desc()).limit(1)
        )
        return result.scalar_one()


async def test_stores_and_returns_decimal(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, Decimal("123.45"))
    assert value == Decimal("123.45")
    assert isinstance(value, Decimal)


async def test_handles_lakh_precision(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, Decimal("1000000.00"))
    assert value == Decimal("1000000.00")


async def test_handles_paisa(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, Decimal("0.01"))
    assert value == Decimal("0.01")


async def test_no_float_drift(engine, amounts_table):
    """0.1 + 0.2 must equal exactly 0.3 when going through Decimal storage."""
    a = await _roundtrip(engine, amounts_table, Decimal("0.1"))
    b = await _roundtrip(engine, amounts_table, Decimal("0.2"))
    assert a + b == Decimal("0.3")


async def test_negative_amount(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, Decimal("-1500.50"))
    assert value == Decimal("-1500.50")


async def test_string_input_coerced(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, "999.99")
    assert value == Decimal("999.99")


async def test_int_input_coerced(engine, amounts_table):
    value = await _roundtrip(engine, amounts_table, 500)
    assert value == Decimal("500")


async def test_none_passthrough(engine):
    metadata = MetaData()
    table = Table(
        "nullable_amounts",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("value", DecimalText),
    )
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    async with AsyncSession(engine) as session:
        await session.execute(insert(table).values(value=None))
        await session.commit()
        result = await session.execute(select(table.c.value))
        assert result.scalar_one() is None
