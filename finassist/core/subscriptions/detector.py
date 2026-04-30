from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, Transaction


def _classify_cadence(days: float) -> str | None:
    if 28 <= days <= 32:
        return "monthly"
    if 88 <= days <= 95:
        return "quarterly"
    if 360 <= days <= 370:
        return "annual"
    return None


def _cadence_days(cadence: str) -> int:
    return {"monthly": 30, "quarterly": 91, "annual": 365}.get(cadence, 30)


async def detect_subscriptions(session: AsyncSession) -> list[Subscription]:
    """Group recent transactions by (account_id, narration_hash); detect recurring."""
    cutoff = date.today() - timedelta(days=183)
    stmt = select(Transaction).where(Transaction.txn_date >= cutoff)
    txns = (await session.execute(stmt)).scalars().all()

    groups: dict[tuple[int, str], list[Transaction]] = defaultdict(list)
    for t in txns:
        groups[(t.account_id, t.narration_hash)].append(t)

    results: list[Subscription] = []

    for (account_id, _hash), group in groups.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda x: x.txn_date)
        amounts = [Decimal(str(t.amount)) for t in group_sorted]
        med_amt = Decimal(str(median([float(a) for a in amounts])))
        if med_amt == 0:
            continue
        # ±5% tolerance
        within = all(
            abs((a - med_amt) / med_amt) <= Decimal("0.05") for a in amounts
        )
        if not within:
            continue

        diffs = [
            (group_sorted[i + 1].txn_date - group_sorted[i].txn_date).days
            for i in range(len(group_sorted) - 1)
        ]
        if not diffs:
            continue
        med_days = float(median(diffs))
        cadence = _classify_cadence(med_days)
        if cadence is None:
            continue

        last_seen = group_sorted[-1].txn_date
        next_expected = last_seen + timedelta(days=int(round(med_days)))
        name = (group_sorted[-1].narration or "").strip()[:50] or f"Auto-{_hash[:8]}"

        existing = (
            await session.execute(select(Subscription).where(Subscription.name == name))
        ).scalar_one_or_none()

        if existing is not None and existing.auto_detected == 0:
            # Don't overwrite manual subscriptions
            continue

        if existing is None:
            sub = Subscription(
                name=name,
                expected_amount=med_amt,
                amount_tolerance_pct=5.0,
                cadence=cadence,
                next_expected_date=next_expected,
                status="active",
                account_id=account_id,
                started_on=group_sorted[0].txn_date,
                auto_detected=1,
            )
            session.add(sub)
            await session.flush()
        else:
            existing.expected_amount = med_amt
            existing.cadence = cadence
            existing.next_expected_date = next_expected
            existing.account_id = account_id
            existing.started_on = existing.started_on or group_sorted[0].txn_date
            existing.auto_detected = 1
            sub = existing

        for t in group_sorted:
            t.subscription_id = sub.id

        results.append(sub)

    await session.flush()
    return results
