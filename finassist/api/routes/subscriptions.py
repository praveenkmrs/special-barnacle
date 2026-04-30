from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.subscriptions.detector import detect_subscriptions
from core.subscriptions.linker import project_next_n
from db.models import Subscription, Transaction

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


class SubscriptionOut(BaseModel):
    id: int
    name: str
    expected_amount: str | None
    amount_tolerance_pct: float
    cadence: str | None
    next_expected_date: date | None
    status: str
    category_id: int | None
    account_id: int | None
    started_on: date | None
    ended_on: date | None
    notes: str | None
    auto_detected: int
    monthly_run_rate: str
    annual_run_rate: str

    @classmethod
    def from_model(cls, s: Subscription) -> "SubscriptionOut":
        amt = Decimal(str(s.expected_amount)) if s.expected_amount is not None else Decimal("0")
        if s.cadence == "monthly":
            monthly = amt
        elif s.cadence == "quarterly":
            monthly = amt / Decimal(3)
        elif s.cadence == "annual":
            monthly = amt / Decimal(12)
        else:
            monthly = Decimal("0")
        annual = monthly * Decimal(12)
        return cls(
            id=s.id,
            name=s.name,
            expected_amount=str(s.expected_amount) if s.expected_amount is not None else None,
            amount_tolerance_pct=s.amount_tolerance_pct,
            cadence=s.cadence,
            next_expected_date=s.next_expected_date,
            status=s.status,
            category_id=s.category_id,
            account_id=s.account_id,
            started_on=s.started_on,
            ended_on=s.ended_on,
            notes=s.notes,
            auto_detected=s.auto_detected,
            monthly_run_rate=str(monthly),
            annual_run_rate=str(annual),
        )


class SubscriptionIn(BaseModel):
    name: str
    expected_amount: Decimal | None = None
    amount_tolerance_pct: float = 5.0
    cadence: str | None = None
    next_expected_date: date | None = None
    status: str = "active"
    category_id: int | None = None
    account_id: int | None = None
    started_on: date | None = None
    ended_on: date | None = None
    notes: str | None = None


class SubscriptionPatch(BaseModel):
    name: str | None = None
    expected_amount: Decimal | None = None
    amount_tolerance_pct: float | None = None
    cadence: str | None = None
    next_expected_date: date | None = None
    status: str | None = None
    category_id: int | None = None
    account_id: int | None = None
    started_on: date | None = None
    ended_on: date | None = None
    notes: str | None = None


class TxnBrief(BaseModel):
    id: int
    account_id: int
    txn_date: date
    amount: str
    type: str
    narration: str
    category_id: int | None


@router.get("")
async def list_subscriptions(
    session: AsyncSession = Depends(get_session),
) -> list[SubscriptionOut]:
    rows = (
        await session.execute(select(Subscription).order_by(Subscription.id))
    ).scalars().all()
    return [SubscriptionOut.from_model(s) for s in rows]


@router.post("", status_code=201)
async def create_subscription(
    payload: SubscriptionIn, session: AsyncSession = Depends(get_session)
) -> SubscriptionOut:
    data = payload.model_dump()
    s = Subscription(**data, auto_detected=0)
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return SubscriptionOut.from_model(s)


@router.patch("/{sub_id}")
async def update_subscription(
    sub_id: int,
    payload: SubscriptionPatch,
    session: AsyncSession = Depends(get_session),
) -> SubscriptionOut:
    s = await session.get(Subscription, sub_id)
    if s is None:
        raise HTTPException(404, "Subscription not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    await session.commit()
    await session.refresh(s)
    return SubscriptionOut.from_model(s)


@router.get("/upcoming")
async def upcoming(
    days: int = 30, session: AsyncSession = Depends(get_session)
) -> list[dict]:
    horizon = date.today() + timedelta(days=days)
    subs = (
        await session.execute(
            select(Subscription).where(Subscription.status == "active")
        )
    ).scalars().all()
    out: list[dict] = []
    for s in subs:
        for due in project_next_n(s, n=12):
            if date.today() <= due <= horizon:
                out.append(
                    {
                        "subscription_id": s.id,
                        "name": s.name,
                        "due_date": due.isoformat(),
                        "amount": str(s.expected_amount) if s.expected_amount is not None else None,
                        "cadence": s.cadence,
                    }
                )
    out.sort(key=lambda r: r["due_date"])
    return out


@router.get("/{sub_id}/transactions")
async def list_subscription_transactions(
    sub_id: int, session: AsyncSession = Depends(get_session)
) -> list[TxnBrief]:
    s = await session.get(Subscription, sub_id)
    if s is None:
        raise HTTPException(404, "Subscription not found")
    rows = (
        await session.execute(
            select(Transaction)
            .where(Transaction.subscription_id == sub_id)
            .order_by(Transaction.txn_date.desc())
        )
    ).scalars().all()
    return [
        TxnBrief(
            id=t.id,
            account_id=t.account_id,
            txn_date=t.txn_date,
            amount=str(t.amount),
            type=t.type,
            narration=t.narration,
            category_id=t.category_id,
        )
        for t in rows
    ]


@router.post("/{sub_id}/link/{txn_id}")
async def link_transaction(
    sub_id: int, txn_id: int, session: AsyncSession = Depends(get_session)
) -> dict:
    s = await session.get(Subscription, sub_id)
    if s is None:
        raise HTTPException(404, "Subscription not found")
    t = await session.get(Transaction, txn_id)
    if t is None:
        raise HTTPException(404, "Transaction not found")
    t.subscription_id = sub_id
    await session.commit()
    return {"linked": True, "subscription_id": sub_id, "transaction_id": txn_id}


@router.post("/detect")
async def run_detect(session: AsyncSession = Depends(get_session)) -> dict:
    subs = await detect_subscriptions(session)
    await session.commit()
    return {"detected": len(subs), "ids": [s.id for s in subs]}
