from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.envelopes.service import (
    compute_envelope_balance,
    manual_envelope_debit,
    split_atm_withdrawal,
)
from db.models import Account

router = APIRouter(prefix="/envelopes", tags=["envelopes"])


class EnvelopeOut(BaseModel):
    id: int
    name: str
    envelope_owner: str | None
    balance: str


class SplitItem(BaseModel):
    account_id: int
    amount: Decimal


class SplitIn(BaseModel):
    parent_txn_id: int
    splits: list[SplitItem]


class DebitIn(BaseModel):
    txn_date: date
    amount: Decimal
    narration: str
    category_id: int


@router.get("")
async def list_envelopes(
    session: AsyncSession = Depends(get_session),
) -> list[EnvelopeOut]:
    rows = (
        await session.execute(
            select(Account)
            .where(Account.type == "cash_envelope")
            .order_by(Account.name)
        )
    ).scalars().all()

    out: list[EnvelopeOut] = []
    for a in rows:
        bal = await compute_envelope_balance(a.id, session)
        out.append(
            EnvelopeOut(
                id=a.id,
                name=a.name,
                envelope_owner=a.envelope_owner,
                balance=str(bal),
            )
        )
    return out


@router.post("/split", status_code=201)
async def split_endpoint(
    payload: SplitIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        legs = await split_atm_withdrawal(
            parent_txn_id=payload.parent_txn_id,
            splits=[s.model_dump() for s in payload.splits],
            session=session,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "parent_txn_id": payload.parent_txn_id,
        "leg_ids": [leg.id for leg in legs],
    }


@router.post("/{account_id}/debit", status_code=201)
async def debit_endpoint(
    account_id: int,
    payload: DebitIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        txn = await manual_envelope_debit(
            account_id=account_id,
            txn_date=payload.txn_date,
            amount=payload.amount,
            narration=payload.narration,
            category_id=payload.category_id,
            session=session,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "id": txn.id,
        "account_id": txn.account_id,
        "txn_date": str(txn.txn_date),
        "amount": str(txn.amount),
        "narration": txn.narration,
        "category_id": txn.category_id,
    }
