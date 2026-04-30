from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Rule, Transaction


@dataclass
class Match:
    rule_id: int
    category_id: int | None
    subscription_id: int | None
    confidence: float
    source: str  # "rule_t1" or "rule_t2"


async def _candidate_rules(
    session: AsyncSession,
    txn: Transaction,
    *,
    statuses: tuple[str, ...],
) -> list[Rule]:
    stmt = (
        select(Rule)
        .where(Rule.status.in_(statuses))
        .where(or_(Rule.account_id.is_(None), Rule.account_id == txn.account_id))
        .where(or_(Rule.txn_type.is_(None), Rule.txn_type == txn.type))
        .order_by(Rule.priority.asc(), Rule.id.asc())
    )
    rules = (await session.execute(stmt)).scalars().all()

    # Filter by amount range
    out: list[Rule] = []
    for r in rules:
        if r.amount_min is not None and txn.amount < r.amount_min:
            continue
        if r.amount_max is not None and txn.amount > r.amount_max:
            continue
        out.append(r)

    # Order by longest pattern first (more specific wins)
    return sorted(out, key=lambda r: len(r.pattern), reverse=True)


async def match_active(session: AsyncSession, txn: Transaction) -> Match | None:
    """Run Tier 1 — only `active` rules."""
    rules = await _candidate_rules(session, txn, statuses=("active",))
    return _first_regex_match(rules, txn, source="rule_t1", confidence=1.0)


async def match_candidate(session: AsyncSession, txn: Transaction) -> Match | None:
    """Run Tier 2 — only `candidate` rules."""
    rules = await _candidate_rules(session, txn, statuses=("candidate",))
    return _first_regex_match(rules, txn, source="rule_t2", confidence=0.85)


def _first_regex_match(
    rules: list[Rule], txn: Transaction, *, source: str, confidence: float
) -> Match | None:
    for r in rules:
        try:
            if re.search(r.pattern, txn.narration, flags=re.IGNORECASE):
                return Match(
                    rule_id=r.id,
                    category_id=r.category_id,
                    subscription_id=r.subscription_id,
                    confidence=confidence,
                    source=source,
                )
        except re.error:
            continue
    return None


async def increment_hit(session: AsyncSession, rule_id: int) -> None:
    await session.execute(
        update(Rule)
        .where(Rule.id == rule_id)
        .values(hit_count=Rule.hit_count + 1, last_hit_at=datetime.utcnow())
    )
