from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Rule, Transaction

PROMOTION_HITS = 5
PROMOTION_AGE_DAYS = 30
CONFLICT_THRESHOLD = 3
BLACKLIST_DAYS = 90


async def promote_eligible_candidates(session: AsyncSession) -> int:
    """Promote candidate rules with ≥5 hits OR ≥30 days old AND zero conflicts.

    Returns count of promoted rules.
    """
    cutoff = datetime.utcnow() - timedelta(days=PROMOTION_AGE_DAYS)
    stmt = select(Rule).where(
        Rule.status == "candidate",
        Rule.conflict_count == 0,
        ((Rule.hit_count >= PROMOTION_HITS) | (Rule.created_at <= cutoff)),
    )
    eligible = (await session.execute(stmt)).scalars().all()

    now = datetime.utcnow()
    for r in eligible:
        r.status = "active"
        r.promoted_at = now

    if eligible:
        # Clear classification-related needs_review on past transactions classified by t2 from these rules
        await session.execute(
            update(Transaction)
            .where(
                Transaction.classification_source == "rule_t2",
                Transaction.review_reason == "classification",
            )
            .values(needs_review=0, review_reason=None)
        )
        await session.commit()

    return len(eligible)


async def record_conflict(session: AsyncSession, rule_id: int) -> None:
    """Increment conflict_count; auto-disable + blacklist on 3rd conflict."""
    rule = await session.get(Rule, rule_id)
    if rule is None:
        return
    rule.conflict_count = (rule.conflict_count or 0) + 1
    if rule.conflict_count >= CONFLICT_THRESHOLD:
        rule.status = "disabled"
        rule.blacklist_until = datetime.utcnow() + timedelta(days=BLACKLIST_DAYS)
    await session.commit()
