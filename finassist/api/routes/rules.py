from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.classifier.promoter import promote_eligible_candidates
from db.models import Rule

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleOut(BaseModel):
    id: int
    pattern: str
    pattern_type: str | None
    amount_min: str | None
    amount_max: str | None
    account_id: int | None
    txn_type: str | None
    category_id: int | None
    subscription_id: int | None
    status: str
    priority: int
    hit_count: int
    conflict_count: int
    last_hit_at: datetime | None
    created_by: str
    created_at: datetime
    promoted_at: datetime | None
    blacklist_until: datetime | None

    @classmethod
    def from_model(cls, r: Rule) -> "RuleOut":
        return cls(
            id=r.id,
            pattern=r.pattern,
            pattern_type=r.pattern_type,
            amount_min=str(r.amount_min) if r.amount_min is not None else None,
            amount_max=str(r.amount_max) if r.amount_max is not None else None,
            account_id=r.account_id,
            txn_type=r.txn_type,
            category_id=r.category_id,
            subscription_id=r.subscription_id,
            status=r.status,
            priority=r.priority,
            hit_count=r.hit_count,
            conflict_count=r.conflict_count,
            last_hit_at=r.last_hit_at,
            created_by=r.created_by,
            created_at=r.created_at,
            promoted_at=r.promoted_at,
            blacklist_until=r.blacklist_until,
        )


class RuleIn(BaseModel):
    pattern: str
    pattern_type: str = "narration"
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_id: int | None = None
    txn_type: str | None = None
    category_id: int | None = None
    subscription_id: int | None = None
    status: str = "active"  # manual rules bypass probation
    priority: int = 100


class RulePatch(BaseModel):
    pattern: str | None = None
    pattern_type: str | None = None
    amount_min: Decimal | None = None
    amount_max: Decimal | None = None
    account_id: int | None = None
    txn_type: str | None = None
    category_id: int | None = None
    subscription_id: int | None = None
    status: str | None = None
    priority: int | None = None


@router.get("")
async def list_rules(
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[RuleOut]:
    stmt = select(Rule).order_by(
        Rule.last_hit_at.is_(None).asc(),
        Rule.last_hit_at.desc(),
        Rule.id.desc(),
    )
    if status is not None:
        stmt = stmt.where(Rule.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return [RuleOut.from_model(r) for r in rows]


@router.post("", status_code=201)
async def create_rule(
    payload: RuleIn, session: AsyncSession = Depends(get_session)
) -> RuleOut:
    r = Rule(**payload.model_dump(), created_by="user")
    session.add(r)
    await session.commit()
    await session.refresh(r)
    return RuleOut.from_model(r)


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: int,
    payload: RulePatch,
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    r = await session.get(Rule, rule_id)
    if r is None:
        raise HTTPException(404, "Rule not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(r, k, v)
    await session.commit()
    await session.refresh(r)
    return RuleOut.from_model(r)


@router.post("/{rule_id}/promote")
async def promote_rule(
    rule_id: int, session: AsyncSession = Depends(get_session)
) -> RuleOut:
    r = await session.get(Rule, rule_id)
    if r is None:
        raise HTTPException(404, "Rule not found")
    r.status = "active"
    r.promoted_at = datetime.utcnow()
    await session.commit()
    await session.refresh(r)
    return RuleOut.from_model(r)


@router.post("/{rule_id}/disable")
async def disable_rule(
    rule_id: int, session: AsyncSession = Depends(get_session)
) -> RuleOut:
    r = await session.get(Rule, rule_id)
    if r is None:
        raise HTTPException(404, "Rule not found")
    r.status = "disabled"
    await session.commit()
    await session.refresh(r)
    return RuleOut.from_model(r)


@router.post("/promote-eligible")
async def promote_eligible(session: AsyncSession = Depends(get_session)) -> dict:
    promoted = await promote_eligible_candidates(session)
    return {"promoted": promoted}
