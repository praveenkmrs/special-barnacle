from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Account, Transaction


@dataclass
class AccountBalance:
    account_id: int
    name: str
    type: str
    bank_code: str | None
    envelope_owner: str | None
    balance: Decimal


async def per_account_balances(session: AsyncSession) -> list[AccountBalance]:
    """opening_balance + sum(credits) − sum(debits) per account."""
    accounts = (await session.execute(select(Account))).scalars().all()
    if not accounts:
        return []

    # Aggregate transactions by account in a single query
    signed = case(
        (Transaction.type == "credit", Transaction.amount),
        else_=-Transaction.amount,
    )
    rows = (
        await session.execute(
            select(Transaction.account_id, func.sum(signed).label("net"))
            .group_by(Transaction.account_id)
        )
    ).all()
    nets: dict[int, Decimal] = {r.account_id: Decimal(r.net or 0) for r in rows}

    out: list[AccountBalance] = []
    for a in accounts:
        opening = a.opening_balance if isinstance(a.opening_balance, Decimal) else Decimal(
            str(a.opening_balance or 0)
        )
        balance = opening + nets.get(a.id, Decimal("0"))
        out.append(
            AccountBalance(
                account_id=a.id,
                name=a.name,
                type=a.type,
                bank_code=a.bank_code,
                envelope_owner=a.envelope_owner,
                balance=balance,
            )
        )
    return out


async def cash_buffer(session: AsyncSession) -> Decimal:
    """Sum of bank + cash_envelope balances. Per plan §2.8."""
    balances = await per_account_balances(session)
    total = Decimal("0")
    for b in balances:
        if b.type in ("bank", "cash_envelope"):
            total += b.balance
    return total


async def capital_deployed(session: AsyncSession) -> tuple[Decimal, Decimal]:
    """Returns (total_invested_cost, current_value)."""
    from db.models import Holding

    rows = (await session.execute(select(Holding))).scalars().all()
    cost = sum((h.total_invested for h in rows), Decimal("0"))
    value = sum((h.current_value or h.total_invested for h in rows), Decimal("0"))
    return cost, value
