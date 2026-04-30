from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.investments.nav_fetcher import latest_nav_for_scheme
from db.models import Holding, HoldingTransaction, Transaction


class InvestmentError(Exception):
    pass


async def buy_units(
    holding_id: int,
    txn_date: date,
    amount: Decimal,
    linked_transaction_id: int | None,
    session: AsyncSession,
) -> HoldingTransaction:
    holding = await session.get(Holding, holding_id)
    if holding is None:
        raise InvestmentError(f"Holding {holding_id} not found")

    nav_row = await latest_nav_for_scheme(session, holding.identifier, on_or_before=txn_date)
    if nav_row is None:
        raise InvestmentError(
            f"No NAV available for scheme {holding.identifier} on or before {txn_date}"
        )
    nav = nav_row.nav
    units = (Decimal(amount) / Decimal(nav))

    ht = HoldingTransaction(
        holding_id=holding_id,
        txn_date=txn_date,
        type="buy",
        units=units,
        price_per_unit=nav,
        amount=Decimal(amount),
        linked_transaction_id=linked_transaction_id,
    )
    session.add(ht)

    holding.units = Decimal(holding.units or 0) + units
    holding.total_invested = Decimal(holding.total_invested or 0) + Decimal(amount)
    if holding.units > 0:
        holding.avg_cost = (Decimal(holding.total_invested) / Decimal(holding.units))

    await session.commit()
    await session.refresh(ht)
    return ht


async def sell_units(
    holding_id: int,
    txn_date: date,
    units: Decimal,
    amount: Decimal,
    linked_transaction_id: int | None,
    session: AsyncSession,
) -> HoldingTransaction:
    holding = await session.get(Holding, holding_id)
    if holding is None:
        raise InvestmentError(f"Holding {holding_id} not found")

    nav_row = await latest_nav_for_scheme(session, holding.identifier, on_or_before=txn_date)
    price = nav_row.nav if nav_row is not None else None

    ht = HoldingTransaction(
        holding_id=holding_id,
        txn_date=txn_date,
        type="sell",
        units=Decimal(units),
        price_per_unit=price,
        amount=Decimal(amount),
        linked_transaction_id=linked_transaction_id,
    )
    session.add(ht)

    holding.units = Decimal(holding.units or 0) - Decimal(units)
    holding.total_invested = Decimal(holding.total_invested or 0) - Decimal(amount)
    if holding.units > 0:
        holding.avg_cost = (Decimal(holding.total_invested) / Decimal(holding.units))
    else:
        holding.avg_cost = None

    await session.commit()
    await session.refresh(ht)
    return ht


async def link_sip_transaction(
    txn_id: int, holding_id: int, session: AsyncSession
) -> HoldingTransaction:
    txn = await session.get(Transaction, txn_id)
    if txn is None:
        raise InvestmentError(f"Transaction {txn_id} not found")
    if txn.type != "debit":
        raise InvestmentError("SIP transaction must be a debit")
    return await buy_units(
        holding_id=holding_id,
        txn_date=txn.txn_date,
        amount=Decimal(txn.amount),
        linked_transaction_id=txn.id,
        session=session,
    )


async def refresh_all_holdings_value(session: AsyncSession) -> int:
    """Update current_nav, current_value for all MF holdings using latest NAV."""
    holdings = (
        await session.execute(select(Holding).where(Holding.instrument_type == "mf"))
    ).scalars().all()
    count = 0
    now = datetime.utcnow()
    for h in holdings:
        nav_row = await latest_nav_for_scheme(session, h.identifier)
        if nav_row is None:
            continue
        h.current_nav = nav_row.nav
        h.current_value = Decimal(h.units or 0) * Decimal(nav_row.nav)
        h.nav_updated_at = now
        count += 1
    await session.commit()
    return count
