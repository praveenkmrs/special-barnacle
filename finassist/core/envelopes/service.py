from __future__ import annotations

import hashlib
import re
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Account, Category, Transaction


_INTER_ACCOUNT_TRANSFER = "Inter-account Transfer"


def _normalize_for_hash(narration: str) -> str:
    if not narration:
        return ""
    return re.sub(r"\s+", " ", narration.lower()).strip()


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def _get_inter_account_transfer_category(session: AsyncSession) -> Category:
    res = await session.execute(
        select(Category).where(Category.name == _INTER_ACCOUNT_TRANSFER)
    )
    cat = res.scalars().first()
    if cat is None:
        raise ValueError(
            f"Required category '{_INTER_ACCOUNT_TRANSFER}' is missing; "
            "ensure default categories are seeded."
        )
    return cat


async def split_atm_withdrawal(
    parent_txn_id: int,
    splits: list[dict],
    session: AsyncSession,
) -> list[Transaction]:
    """Split an ATM withdrawal (parent debit txn) across cash_envelope accounts.

    Each split is `{account_id: int, amount: Decimal | str | number}`. Sum of
    splits must not exceed the parent txn amount. All target accounts must be
    of type cash_envelope.
    """
    parent = await session.get(Transaction, parent_txn_id)
    if parent is None:
        raise ValueError(f"Parent transaction {parent_txn_id} not found")
    if parent.type != "debit":
        raise ValueError("Parent transaction must be a debit")

    if not splits:
        raise ValueError("At least one split is required")

    parsed: list[tuple[int, Decimal]] = []
    for s in splits:
        acc_id = int(s["account_id"])
        amt = Decimal(str(s["amount"]))
        if amt <= 0:
            raise ValueError("Split amounts must be positive")
        parsed.append((acc_id, amt))

    total_split = sum((a for _, a in parsed), Decimal("0"))
    if total_split > parent.amount:
        raise ValueError(
            f"Sum of splits ({total_split}) exceeds parent amount ({parent.amount})"
        )

    # Validate all envelope accounts exist and are cash_envelope
    account_ids = [a for a, _ in parsed]
    res = await session.execute(select(Account).where(Account.id.in_(account_ids)))
    accounts = {a.id: a for a in res.scalars().all()}
    for acc_id in account_ids:
        if acc_id not in accounts:
            raise ValueError(f"Envelope account {acc_id} not found")
        if accounts[acc_id].type != "cash_envelope":
            raise ValueError(
                f"Account {acc_id} is not a cash_envelope (got {accounts[acc_id].type})"
            )

    transfer_cat = await _get_inter_account_transfer_category(session)

    # Flip the parent txn to a transfer
    parent.is_transfer = 1
    parent.category_id = transfer_cat.id
    parent.needs_review = 0
    parent.review_reason = None
    parent.classification_source = "manual"
    parent.classification_confidence = 1.0
    parent.transfer_pair_id = None  # cleared; multi-leg below

    short_narr = (parent.narration or "")[:40]

    created: list[Transaction] = []
    for acc_id, amt in parsed:
        narration = f"Cash split from {short_narr}"
        leg = Transaction(
            account_id=acc_id,
            txn_date=parent.txn_date,
            amount=amt,
            type="credit",
            narration=narration,
            narration_hash=_sha(f"envelope_split:{parent.id}:{acc_id}"),
            category_id=transfer_cat.id,
            is_transfer=1,
            transfer_pair_id=parent.id,
            classification_source="manual",
            classification_confidence=1.0,
            needs_review=0,
        )
        session.add(leg)
        created.append(leg)

    await session.flush()

    # If there is a single split, mirror parent.transfer_pair_id back to it.
    if len(created) == 1:
        parent.transfer_pair_id = created[0].id

    await session.commit()
    for leg in created:
        await session.refresh(leg)
    await session.refresh(parent)
    return created


async def manual_envelope_debit(
    account_id: int,
    txn_date: date,
    amount: Decimal,
    narration: str,
    category_id: int,
    session: AsyncSession,
) -> Transaction:
    """Create a debit transaction on a cash_envelope account."""
    acct = await session.get(Account, account_id)
    if acct is None:
        raise ValueError(f"Account {account_id} not found")
    if acct.type != "cash_envelope":
        raise ValueError(f"Account {account_id} is not a cash_envelope")

    amt = Decimal(str(amount))
    if amt <= 0:
        raise ValueError("Amount must be positive")

    cat = await session.get(Category, category_id)
    if cat is None:
        raise ValueError(f"Category {category_id} not found")

    narration_clean = _normalize_for_hash(narration)
    narration_hash = _sha(narration_clean)

    txn = Transaction(
        account_id=account_id,
        txn_date=txn_date,
        amount=amt,
        type="debit",
        narration=narration,
        narration_hash=narration_hash,
        category_id=category_id,
        classification_source="manual",
        classification_confidence=1.0,
        is_transfer=0,
        needs_review=0,
    )
    session.add(txn)
    await session.commit()
    await session.refresh(txn)
    return txn


async def compute_envelope_balance(
    account_id: int, session: AsyncSession
) -> Decimal:
    """Compute envelope balance = opening_balance + credits - debits."""
    acct = await session.get(Account, account_id)
    if acct is None:
        raise ValueError(f"Account {account_id} not found")

    res = await session.execute(
        select(Transaction).where(Transaction.account_id == account_id)
    )
    txns = res.scalars().all()

    credits = sum(
        (t.amount for t in txns if t.type == "credit"), Decimal("0")
    )
    debits = sum(
        (t.amount for t in txns if t.type == "debit"), Decimal("0")
    )
    opening = acct.opening_balance or Decimal("0")
    return Decimal(opening) + credits - debits
