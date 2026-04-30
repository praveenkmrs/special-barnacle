from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.parsing.raw_transaction import RawTransaction
from db.models import Transaction


class DupVerdict(Enum):
    CLEAN = "clean"
    DEFINITE_DUPLICATE = "definite_duplicate"
    AMBIGUOUS = "ambiguous"


@dataclass
class DupCheckResult:
    verdict: DupVerdict
    matched_existing_ids: list[int]


async def check_duplicate(
    incoming: RawTransaction,
    account_id: int,
    session: AsyncSession,
) -> DupCheckResult:
    """3-tier duplicate detection (plan §11.5).

    Tier A (definite): same reference OR same balance_after → silently skip.
    Tier B (clean): refs/balances both present and DIFFER → distinct, insert.
    Tier C (ambiguous): mix of nulls/etc → insert + flag both for review.
    """
    stmt = select(Transaction).where(
        Transaction.account_id == account_id,
        Transaction.txn_date == incoming.txn_date,
        Transaction.amount == incoming.amount,
        Transaction.type == incoming.type,
        Transaction.narration_hash == incoming.narration_hash,
    )
    matches = (await session.execute(stmt)).scalars().all()

    if not matches:
        return DupCheckResult(DupVerdict.CLEAN, [])

    # Tier A: definite duplicate (any single confident match)
    for m in matches:
        if incoming.reference and m.reference and incoming.reference == m.reference:
            return DupCheckResult(DupVerdict.DEFINITE_DUPLICATE, [m.id])
        if incoming.balance_after is not None and m.balance_after is not None:
            if incoming.balance_after == m.balance_after:
                return DupCheckResult(DupVerdict.DEFINITE_DUPLICATE, [m.id])

    # Tier B: definitely distinct (any single confident "no")
    for m in matches:
        if incoming.reference and m.reference and incoming.reference != m.reference:
            return DupCheckResult(DupVerdict.CLEAN, [])
        if incoming.balance_after is not None and m.balance_after is not None:
            if incoming.balance_after != m.balance_after:
                return DupCheckResult(DupVerdict.CLEAN, [])

    # Tier C: ambiguous
    return DupCheckResult(DupVerdict.AMBIGUOUS, [m.id for m in matches])
