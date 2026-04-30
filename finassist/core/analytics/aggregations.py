from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Category, Transaction


@dataclass
class CategoryAggregate:
    category_id: int | None
    category_name: str | None
    parent_id: int | None
    parent_name: str | None
    is_income: int
    is_transfer: int
    debit_total: Decimal
    credit_total: Decimal


async def category_breakdown(
    session: AsyncSession,
    *,
    from_date: date,
    to_date: date,
    include_transfers: bool = False,
) -> list[CategoryAggregate]:
    """Aggregate debit/credit totals per category over a period.

    By default excludes transfer categories from the result (plan §2.2).
    """
    debit_sum = func.sum(case((Transaction.type == "debit", Transaction.amount), else_=0))
    credit_sum = func.sum(case((Transaction.type == "credit", Transaction.amount), else_=0))

    parent = Category.__table__.alias("parent")

    stmt = (
        select(
            Category.id.label("category_id"),
            Category.name.label("category_name"),
            Category.parent_id.label("parent_id"),
            parent.c.name.label("parent_name"),
            Category.is_income,
            Category.is_transfer,
            debit_sum.label("debit_total"),
            credit_sum.label("credit_total"),
        )
        .select_from(Transaction)
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .join(parent, Category.parent_id == parent.c.id, isouter=True)
        .where(Transaction.txn_date >= from_date, Transaction.txn_date <= to_date)
        .where(Transaction.is_transfer == 0)
        .group_by(
            Category.id,
            Category.name,
            Category.parent_id,
            parent.c.name,
            Category.is_income,
            Category.is_transfer,
        )
    )

    rows = (await session.execute(stmt)).all()

    out: list[CategoryAggregate] = []
    for r in rows:
        if not include_transfers and r.is_transfer:
            continue
        out.append(
            CategoryAggregate(
                category_id=r.category_id,
                category_name=r.category_name,
                parent_id=r.parent_id,
                parent_name=r.parent_name,
                is_income=r.is_income or 0,
                is_transfer=r.is_transfer or 0,
                debit_total=Decimal(r.debit_total or 0),
                credit_total=Decimal(r.credit_total or 0),
            )
        )
    return out


async def net_cashflow(
    session: AsyncSession, *, from_date: date, to_date: date
) -> tuple[Decimal, Decimal, Decimal]:
    """Returns (income, expenses, net) over [from_date, to_date], excluding transfers."""
    aggs = await category_breakdown(
        session, from_date=from_date, to_date=to_date, include_transfers=False
    )
    income = sum((a.credit_total for a in aggs if a.is_income), Decimal("0"))
    expenses = sum((a.debit_total for a in aggs if not a.is_income), Decimal("0"))
    return income, expenses, income - expenses
