from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.classifier.pattern_extractor import extract_patterns
from core.classifier.promoter import record_conflict
from db.models import Rule, Transaction


async def manual_classify(
    session: AsyncSession,
    txn: Transaction,
    category_id: int,
) -> None:
    """User has manually classified a transaction.

    - Apply the category, mark source=manual, clear classification review.
    - If a previous T1/T2 rule had auto-classified this row to a different category,
      record a conflict against that rule.
    - Generate candidate patterns from the narration.
    """
    previous_source = txn.classification_source
    previous_category = txn.category_id

    if (
        previous_source in ("rule_t1", "rule_t2")
        and previous_category is not None
        and previous_category != category_id
    ):
        # Find the rule that matched and record a conflict
        # We don't store rule_id on the transaction, so we re-derive: find any active/candidate
        # rule that pattern-matches the narration and points at the wrong category.
        import re

        offending = (
            await session.execute(
                select(Rule).where(
                    Rule.status.in_(("active", "candidate")),
                    Rule.category_id == previous_category,
                )
            )
        ).scalars().all()
        for r in offending:
            try:
                if re.search(r.pattern, txn.narration, flags=re.IGNORECASE):
                    await record_conflict(session, r.id)
                    break
            except re.error:
                continue

    txn.category_id = category_id
    txn.classification_source = "manual"
    txn.classification_confidence = 1.0
    if txn.review_reason == "classification":
        txn.needs_review = 0
        txn.review_reason = None

    # Generate candidate patterns
    for pat in extract_patterns(txn.narration):
        # Upsert: skip if an identical pattern already exists for the same category
        existing = (
            await session.execute(
                select(Rule).where(
                    Rule.pattern == pat.pattern,
                    Rule.category_id == category_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        # Skip if pattern is in blacklist window
        blacklisted = (
            await session.execute(
                select(Rule).where(
                    Rule.pattern == pat.pattern,
                    Rule.status == "disabled",
                    Rule.blacklist_until.is_not(None),
                    Rule.blacklist_until > datetime.utcnow(),
                )
            )
        ).scalar_one_or_none()
        if blacklisted is not None:
            continue

        session.add(
            Rule(
                pattern=pat.pattern,
                pattern_type=pat.pattern_type,
                txn_type=txn.type,
                category_id=category_id,
                status="candidate",
                priority=100,
                created_by="user",
            )
        )

    await session.commit()
