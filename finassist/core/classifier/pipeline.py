from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from core.classifier import tier1_rules, tier3_fuzzy
from db.models import Transaction


async def classify_transaction(session: AsyncSession, txn: Transaction) -> bool:
    """Run Tier 1 → Tier 2 → Tier 3 pipeline. Returns True if classified."""
    # Tier 1 — high confidence, clears classification review unconditionally
    match = await tier1_rules.match_active(session, txn)
    if match is not None:
        txn.category_id = match.category_id
        txn.subscription_id = match.subscription_id
        txn.classification_source = match.source
        txn.classification_confidence = match.confidence
        if txn.review_reason in (None, "classification"):
            txn.needs_review = 0
            txn.review_reason = None
        await tier1_rules.increment_hit(session, match.rule_id)
        return True

    # Tier 2
    match2 = await tier1_rules.match_candidate(session, txn)
    if match2 is not None:
        txn.category_id = match2.category_id
        txn.subscription_id = match2.subscription_id
        txn.classification_source = match2.source
        txn.classification_confidence = match2.confidence
        # T2 keeps the row in review until the rule promotes
        txn.needs_review = 1
        if not txn.review_reason:
            txn.review_reason = "classification"
        await tier1_rules.increment_hit(session, match2.rule_id)
        return True

    # Tier 3 — fuzzy. >=0.85 confidence is treated as auto-classified.
    fuzzy = await tier3_fuzzy.fuzzy_classify(session, txn)
    if fuzzy is not None and fuzzy.category_id is not None:
        txn.category_id = fuzzy.category_id
        txn.classification_source = "fuzzy_t3"
        txn.classification_confidence = fuzzy.confidence
        if txn.review_reason in (None, "classification"):
            txn.needs_review = 0
            txn.review_reason = None
        return True

    # No match — surface for review with suggestions
    if fuzzy is not None and fuzzy.suggestions:
        txn.notes = json.dumps(
            {
                "fuzzy_top3": [
                    {"category_id": cid, "score": round(s, 4)}
                    for cid, s in fuzzy.suggestions
                ]
            }
        )
    txn.classification_source = "unclassified"
    if not txn.review_reason:
        txn.review_reason = "classification"
    txn.needs_review = 1
    return False


async def classify_unclassified_batch(
    session: AsyncSession, limit: int = 500
) -> dict[str, int]:
    """Classify all unclassified-or-needs-review transactions. Used post-import."""
    from sqlalchemy import select

    stmt = (
        select(Transaction)
        .where(
            (Transaction.classification_source == "unclassified")
            | (Transaction.review_reason == "classification")
        )
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    classified = 0
    for r in rows:
        if await classify_transaction(session, r):
            classified += 1
    await session.commit()
    return {"examined": len(rows), "classified": classified}
