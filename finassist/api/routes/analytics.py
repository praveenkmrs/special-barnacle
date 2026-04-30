from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.analytics.aggregations import category_breakdown, net_cashflow
from core.analytics.balances import capital_deployed, cash_buffer, per_account_balances
from db.models import Subscription, Transaction

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _default_from() -> date:
    return date.today() - timedelta(days=90)


def _default_to() -> date:
    return date.today()


class AccountBalanceOut(BaseModel):
    account_id: int
    name: str
    type: str
    bank_code: str | None
    envelope_owner: str | None
    balance: str


class CategoryAggOut(BaseModel):
    category_id: int | None
    category_name: str | None
    parent_id: int | None
    parent_name: str | None
    is_income: int
    is_transfer: int
    debit_total: str
    credit_total: str


class DashboardOut(BaseModel):
    period_from: date
    period_to: date
    cash_buffer: str
    capital_deployed_cost: str
    capital_deployed_value: str
    net_cashflow: str
    income: str
    expenses: str
    accounts: list[AccountBalanceOut]
    expense_breakdown: list[CategoryAggOut]
    subscription_run_rate_monthly: str
    subscription_run_rate_annual: str
    review_queue_count: int


@router.get("/dashboard")
async def dashboard(
    from_date: date = Query(default_factory=_default_from, alias="from"),
    to_date: date = Query(default_factory=_default_to, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> DashboardOut:
    cb = await cash_buffer(session)
    cost, value = await capital_deployed(session)
    income, expenses, net = await net_cashflow(session, from_date=from_date, to_date=to_date)
    accounts = await per_account_balances(session)
    breakdown = await category_breakdown(
        session, from_date=from_date, to_date=to_date, include_transfers=False
    )

    # Subscription run-rate
    subs = (
        await session.execute(select(Subscription).where(Subscription.status == "active"))
    ).scalars().all()
    monthly = 0
    annual = 0
    from decimal import Decimal as D

    monthly_d = D("0")
    annual_d = D("0")
    for s in subs:
        if s.expected_amount is None:
            continue
        amt = s.expected_amount
        if s.cadence == "monthly":
            monthly_d += amt
            annual_d += amt * 12
        elif s.cadence == "quarterly":
            monthly_d += amt / 3
            annual_d += amt * 4
        elif s.cadence == "annual":
            monthly_d += amt / 12
            annual_d += amt

    review_count = (
        await session.execute(
            select(Transaction).where(Transaction.needs_review == 1)
        )
    ).scalars().all()

    return DashboardOut(
        period_from=from_date,
        period_to=to_date,
        cash_buffer=str(cb),
        capital_deployed_cost=str(cost),
        capital_deployed_value=str(value),
        net_cashflow=str(net),
        income=str(income),
        expenses=str(expenses),
        accounts=[
            AccountBalanceOut(
                account_id=a.account_id,
                name=a.name,
                type=a.type,
                bank_code=a.bank_code,
                envelope_owner=a.envelope_owner,
                balance=str(a.balance),
            )
            for a in accounts
        ],
        expense_breakdown=[
            CategoryAggOut(
                **{
                    **asdict(b),
                    "debit_total": str(b.debit_total),
                    "credit_total": str(b.credit_total),
                }
            )
            for b in breakdown
            if not b.is_income
        ],
        subscription_run_rate_monthly=str(monthly_d),
        subscription_run_rate_annual=str(annual_d),
        review_queue_count=len(review_count),
    )


@router.get("/categories")
async def categories_breakdown(
    from_date: date = Query(default_factory=_default_from, alias="from"),
    to_date: date = Query(default_factory=_default_to, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> list[CategoryAggOut]:
    rows = await category_breakdown(
        session, from_date=from_date, to_date=to_date, include_transfers=False
    )
    return [
        CategoryAggOut(
            **{
                **asdict(r),
                "debit_total": str(r.debit_total),
                "credit_total": str(r.credit_total),
            }
        )
        for r in rows
    ]


@router.get("/cashflow")
async def cashflow(
    from_date: date = Query(default_factory=_default_from, alias="from"),
    to_date: date = Query(default_factory=_default_to, alias="to"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    income, expenses, net = await net_cashflow(session, from_date=from_date, to_date=to_date)
    return {
        "period_from": from_date.isoformat(),
        "period_to": to_date.isoformat(),
        "income": str(income),
        "expenses": str(expenses),
        "net": str(net),
    }
