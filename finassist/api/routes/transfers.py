from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.transfers.pair_matcher import (
    confirm_pair,
    reject_pair,
    stage_pairs_for_review,
)
from db.models import Transaction

router = APIRouter(prefix="/transfers", tags=["transfers"])


class TransferTxn(BaseModel):
    id: int
    account_id: int
    txn_date: date
    amount: str
    type: str
    narration: str
    reference: str | None
    transfer_pair_id: int | None


class TransferCandidate(BaseModel):
    debit: TransferTxn
    credit: TransferTxn


def _to_model(t: Transaction) -> TransferTxn:
    return TransferTxn(
        id=t.id,
        account_id=t.account_id,
        txn_date=t.txn_date,
        amount=str(t.amount),
        type=t.type,
        narration=t.narration,
        reference=t.reference,
        transfer_pair_id=t.transfer_pair_id,
    )


@router.get("/candidates")
async def list_candidates(
    session: AsyncSession = Depends(get_session),
) -> list[TransferCandidate]:
    rows = (
        await session.execute(
            select(Transaction)
            .where(Transaction.needs_review == 1)
            .where(Transaction.review_reason == "transfer")
            .order_by(Transaction.id)
        )
    ).scalars().all()

    by_id: dict[int, Transaction] = {t.id: t for t in rows}
    seen: set[int] = set()
    out: list[TransferCandidate] = []
    for t in rows:
        if t.id in seen:
            continue
        if t.transfer_pair_id is None or t.transfer_pair_id not in by_id:
            continue
        other = by_id[t.transfer_pair_id]
        if other.id in seen:
            continue
        debit = t if t.type == "debit" else other
        credit = other if t.type == "debit" else t
        if debit.type != "debit" or credit.type != "credit":
            continue
        out.append(
            TransferCandidate(debit=_to_model(debit), credit=_to_model(credit))
        )
        seen.add(t.id)
        seen.add(other.id)
    return out


@router.post("/stage")
async def stage(session: AsyncSession = Depends(get_session)) -> dict[str, int]:
    count = await stage_pairs_for_review(session)
    return {"staged": count}


@router.post("/{txn_id}/confirm")
async def confirm(
    txn_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    t = (
        await session.execute(select(Transaction).where(Transaction.id == txn_id))
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Transaction not found")
    if t.transfer_pair_id is None:
        raise HTTPException(400, "Transaction has no staged transfer pair")
    debit_id = t.id if t.type == "debit" else t.transfer_pair_id
    credit_id = t.transfer_pair_id if t.type == "debit" else t.id
    await confirm_pair(debit_id, credit_id, session)
    return {"debit_id": debit_id, "credit_id": credit_id}


@router.post("/{txn_id}/reject")
async def reject(
    txn_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    t = (
        await session.execute(select(Transaction).where(Transaction.id == txn_id))
    ).scalar_one_or_none()
    if t is None:
        raise HTTPException(404, "Transaction not found")
    if t.transfer_pair_id is None:
        raise HTTPException(400, "Transaction has no staged transfer pair")
    debit_id = t.id if t.type == "debit" else t.transfer_pair_id
    credit_id = t.transfer_pair_id if t.type == "debit" else t.id
    await reject_pair(debit_id, credit_id, session)
    return {"debit_id": debit_id, "credit_id": credit_id}
