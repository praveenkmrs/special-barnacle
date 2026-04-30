from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.models import Transaction

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionOut(BaseModel):
    id: int
    account_id: int
    txn_date: date
    amount: str
    type: str
    narration: str
    balance_after: str | None
    reference: str | None
    category_id: int | None
    subscription_id: int | None
    is_transfer: int
    classification_source: str | None
    classification_confidence: float | None
    needs_review: int
    review_reason: str | None
    dup_group_id: int | None
    notes: str | None
    source_file: str | None

    @classmethod
    def from_model(cls, t: Transaction) -> "TransactionOut":
        return cls(
            id=t.id,
            account_id=t.account_id,
            txn_date=t.txn_date,
            amount=str(t.amount),
            type=t.type,
            narration=t.narration,
            balance_after=str(t.balance_after) if t.balance_after is not None else None,
            reference=t.reference,
            category_id=t.category_id,
            subscription_id=t.subscription_id,
            is_transfer=t.is_transfer,
            classification_source=t.classification_source,
            classification_confidence=t.classification_confidence,
            needs_review=t.needs_review,
            review_reason=t.review_reason,
            dup_group_id=t.dup_group_id,
            notes=t.notes,
            source_file=t.source_file,
        )


@router.get("")
async def list_transactions(
    account_id: int | None = None,
    category_id: int | None = None,
    needs_review: int | None = None,
    review_reason: str | None = None,
    is_transfer: int | None = None,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[TransactionOut]:
    stmt = select(Transaction).order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if needs_review is not None:
        stmt = stmt.where(Transaction.needs_review == needs_review)
    if review_reason is not None:
        stmt = stmt.where(Transaction.review_reason == review_reason)
    if is_transfer is not None:
        stmt = stmt.where(Transaction.is_transfer == is_transfer)
    if from_date is not None:
        stmt = stmt.where(Transaction.txn_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(Transaction.txn_date <= to_date)

    rows = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    return [TransactionOut.from_model(r) for r in rows]


@router.get("/{txn_id}")
async def get_transaction(
    txn_id: int, session: AsyncSession = Depends(get_session)
) -> TransactionOut:
    t = await session.get(Transaction, txn_id)
    if t is None:
        raise HTTPException(404, "Transaction not found")
    return TransactionOut.from_model(t)


class ClassifyIn(BaseModel):
    category_id: int


@router.post("/{txn_id}/classify")
async def classify_transaction(
    txn_id: int,
    payload: ClassifyIn,
    session: AsyncSession = Depends(get_session),
) -> TransactionOut:
    t = await session.get(Transaction, txn_id)
    if t is None:
        raise HTTPException(404, "Transaction not found")
    t.category_id = payload.category_id
    t.classification_source = "manual"
    t.classification_confidence = 1.0
    if t.review_reason == "classification":
        t.needs_review = 0
        t.review_reason = None
    await session.commit()
    await session.refresh(t)
    return TransactionOut.from_model(t)
