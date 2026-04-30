from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from db.models import Category, Transaction


async def _get_transfer_category_id(session: AsyncSession) -> int | None:
    """Find the 'Inter-account Transfer' child of the 'Transfers' parent."""
    Parent = aliased(Category)
    row = (
        await session.execute(
            select(Category.id)
            .join(Parent, Category.parent_id == Parent.id)
            .where(Category.name == "Inter-account Transfer")
            .where(Parent.name == "Transfers")
        )
    ).first()
    return row[0] if row else None


def _eligible(t: Transaction, transfer_cat_id: int | None) -> bool:
    """Both legs must be unclassified or already in transfer category, and currently is_transfer=0."""
    if t.is_transfer:
        return False
    if t.transfer_pair_id is not None:
        return False
    if t.dup_group_id is not None:
        return False
    if t.category_id is None:
        return True
    if transfer_cat_id is not None and t.category_id == transfer_cat_id:
        return True
    return False


async def find_pair_candidates(
    session: AsyncSession,
) -> list[tuple[Transaction, Transaction]]:
    """Find debit-credit pairs across DIFFERENT accounts within 72 hours, equal amounts.

    Does not mutate the database.
    """
    transfer_cat_id = await _get_transfer_category_id(session)

    debits = (
        await session.execute(
            select(Transaction).where(Transaction.type == "debit")
        )
    ).scalars().all()
    credits = (
        await session.execute(
            select(Transaction).where(Transaction.type == "credit")
        )
    ).scalars().all()

    eligible_debits = [t for t in debits if _eligible(t, transfer_cat_id)]
    eligible_credits = [t for t in credits if _eligible(t, transfer_cat_id)]

    used_credit_ids: set[int] = set()
    used_debit_ids: set[int] = set()
    pairs: list[tuple[Transaction, Transaction]] = []

    for d in eligible_debits:
        if d.id in used_debit_ids:
            continue
        for c in eligible_credits:
            if c.id in used_credit_ids:
                continue
            if c.account_id == d.account_id:
                continue
            if c.amount != d.amount:
                continue
            delta = abs((c.txn_date - d.txn_date).days)
            if delta > 3:
                continue
            # within 72 hours: 3 calendar days either direction
            pairs.append((d, c))
            used_debit_ids.add(d.id)
            used_credit_ids.add(c.id)
            break

    return pairs


async def stage_pairs_for_review(session: AsyncSession) -> int:
    """Find candidates, mark both rows needs_review=1 with review_reason='transfer'.

    Sets reciprocal transfer_pair_id on each. Skips pairs already staged.
    Returns count of newly staged pairs.
    """
    pairs = await find_pair_candidates(session)
    staged = 0
    for debit, credit in pairs:
        # skip if either is already linked
        if debit.transfer_pair_id is not None or credit.transfer_pair_id is not None:
            continue
        debit.needs_review = 1
        debit.review_reason = "transfer"
        debit.transfer_pair_id = credit.id
        credit.needs_review = 1
        credit.review_reason = "transfer"
        credit.transfer_pair_id = debit.id
        staged += 1
    await session.commit()
    return staged


async def confirm_pair(
    debit_id: int, credit_id: int, session: AsyncSession
) -> None:
    transfer_cat_id = await _get_transfer_category_id(session)
    await session.execute(
        update(Transaction)
        .where(Transaction.id.in_([debit_id, credit_id]))
        .values(
            is_transfer=1,
            category_id=transfer_cat_id,
            needs_review=0,
            review_reason=None,
        )
    )
    # Ensure transfer_pair_id is reciprocal
    await session.execute(
        update(Transaction)
        .where(Transaction.id == debit_id)
        .values(transfer_pair_id=credit_id)
    )
    await session.execute(
        update(Transaction)
        .where(Transaction.id == credit_id)
        .values(transfer_pair_id=debit_id)
    )
    await session.commit()


async def reject_pair(
    debit_id: int, credit_id: int, session: AsyncSession
) -> None:
    await session.execute(
        update(Transaction)
        .where(Transaction.id.in_([debit_id, credit_id]))
        .values(
            transfer_pair_id=None,
            is_transfer=0,
            needs_review=0,
            review_reason=None,
        )
    )
    await session.commit()


__all__ = [
    "find_pair_candidates",
    "stage_pairs_for_review",
    "confirm_pair",
    "reject_pair",
]
