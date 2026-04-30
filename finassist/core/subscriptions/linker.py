from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, Transaction


_CADENCE_DAYS = {"monthly": 30, "quarterly": 91, "annual": 365}


def _cadence_days(cadence: str | None) -> int:
    if cadence is None:
        return 30
    return _CADENCE_DAYS.get(cadence, 30)


async def link_recent_to_subscriptions(session: AsyncSession) -> int:
    """For each active subscription, link unlinked transactions matching its signature."""
    subs = (
        await session.execute(
            select(Subscription).where(Subscription.status == "active")
        )
    ).scalars().all()

    linked_count = 0
    for sub in subs:
        if sub.account_id is None:
            continue
        # Find a known linked transaction to grab its narration_hash signature
        sig_txn = (
            await session.execute(
                select(Transaction)
                .where(Transaction.subscription_id == sub.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if sig_txn is None:
            continue
        narration_hash = sig_txn.narration_hash

        # Find unlinked txns with same signature on same account
        candidates = (
            await session.execute(
                select(Transaction).where(
                    Transaction.account_id == sub.account_id,
                    Transaction.narration_hash == narration_hash,
                    Transaction.subscription_id.is_(None),
                )
            )
        ).scalars().all()
        for t in candidates:
            t.subscription_id = sub.id
            linked_count += 1

    await session.flush()
    return linked_count


def project_next_n(sub: Subscription, n: int = 12) -> list[date]:
    """Project next n occurrences from sub.next_expected_date based on cadence."""
    if sub.next_expected_date is None or sub.cadence is None:
        return []
    step = _cadence_days(sub.cadence)
    out: list[date] = []
    current = sub.next_expected_date
    for _ in range(n):
        out.append(current)
        current = current + timedelta(days=step)
    return out
