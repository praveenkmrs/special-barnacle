from __future__ import annotations

from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.models import Transaction

router = APIRouter(prefix="/duplicates", tags=["duplicates"])


class DupRow(BaseModel):
    id: int
    account_id: int
    txn_date: date
    amount: str
    type: str
    narration: str
    balance_after: str | None
    reference: str | None
    source_file: str | None
    source_page: int | None


class DupGroup(BaseModel):
    group_id: int
    rows: list[DupRow]


@router.get("/groups")
async def list_dup_groups(session: AsyncSession = Depends(get_session)) -> list[DupGroup]:
    rows = (
        await session.execute(
            select(Transaction)
            .where(Transaction.dup_group_id.is_not(None))
            .order_by(Transaction.dup_group_id, Transaction.id)
        )
    ).scalars().all()

    groups: dict[int, list[Transaction]] = defaultdict(list)
    for r in rows:
        groups[r.dup_group_id].append(r)

    return [
        DupGroup(
            group_id=gid,
            rows=[
                DupRow(
                    id=t.id,
                    account_id=t.account_id,
                    txn_date=t.txn_date,
                    amount=str(t.amount),
                    type=t.type,
                    narration=t.narration,
                    balance_after=str(t.balance_after) if t.balance_after else None,
                    reference=t.reference,
                    source_file=t.source_file,
                    source_page=t.source_page,
                )
                for t in members
            ],
        )
        for gid, members in groups.items()
    ]


@router.post("/{group_id}/keep-all")
async def keep_all(
    group_id: int, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    res = await session.execute(
        update(Transaction)
        .where(Transaction.dup_group_id == group_id)
        .values(dup_group_id=None, review_reason=None, needs_review=0)
    )
    await session.commit()
    return {"affected": res.rowcount or 0}


class ResolveIn(BaseModel):
    keep_ids: list[int]
    delete_ids: list[int]


@router.post("/{group_id}/resolve")
async def resolve(
    group_id: int,
    payload: ResolveIn,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    members = (
        await session.execute(
            select(Transaction).where(Transaction.dup_group_id == group_id)
        )
    ).scalars().all()
    member_ids = {t.id for t in members}
    if not member_ids:
        raise HTTPException(404, "Duplicate group not found")
    if not set(payload.keep_ids).issubset(member_ids) or not set(
        payload.delete_ids
    ).issubset(member_ids):
        raise HTTPException(400, "Some IDs are not in this duplicate group")

    if payload.delete_ids:
        await session.execute(
            delete(Transaction).where(Transaction.id.in_(payload.delete_ids))
        )
    if payload.keep_ids:
        await session.execute(
            update(Transaction)
            .where(Transaction.id.in_(payload.keep_ids))
            .values(dup_group_id=None, review_reason=None, needs_review=0)
        )
    await session.commit()
    return {"deleted": len(payload.delete_ids), "kept": len(payload.keep_ids)}
