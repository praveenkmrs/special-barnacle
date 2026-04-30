from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from core.classifier.manual import manual_classify
from core.classifier.pipeline import classify_transaction
from core.classifier.promoter import promote_eligible_candidates
from db.models import Rule, Transaction


async def _make_txn(
    session, *, account_id: int, narration: str, amount: str = "100", type_: str = "debit"
) -> Transaction:
    t = Transaction(
        account_id=account_id,
        txn_date=date(2024, 1, 1),
        amount=Decimal(amount),
        type=type_,
        narration=narration,
        narration_hash=narration,  # OK for test
        classification_source="unclassified",
        needs_review=1,
    )
    session.add(t)
    await session.flush()
    return t


async def test_tier1_active_rule_matches(db, account_id, category_lookup):
    cat = category_lookup["Food Delivery"]
    async with db() as session:
        session.add(
            Rule(
                pattern="SWIGGY",
                pattern_type="token",
                category_id=cat,
                status="active",
                priority=100,
                created_by="user",
            )
        )
        await session.flush()
        t = await _make_txn(session, account_id=account_id, narration="UPI-SWIGGY-YESB-1-")
        ok = await classify_transaction(session, t)
        assert ok is True
        assert t.category_id == cat
        assert t.classification_source == "rule_t1"
        assert t.needs_review == 0


async def test_tier2_candidate_keeps_review_flag(db, account_id, category_lookup):
    cat = category_lookup["Eating Out"]
    async with db() as session:
        session.add(
            Rule(
                pattern="MCDONALD",
                pattern_type="token",
                category_id=cat,
                status="candidate",
                priority=100,
                created_by="user",
            )
        )
        await session.flush()
        t = await _make_txn(session, account_id=account_id, narration="UPI-MCDONALDS-OK-1-")
        ok = await classify_transaction(session, t)
        assert ok is True
        assert t.classification_source == "rule_t2"
        assert t.needs_review == 1
        assert t.review_reason == "classification"


async def test_unmatched_left_for_review(db, account_id):
    async with db() as session:
        t = await _make_txn(session, account_id=account_id, narration="UPI-UNKNOWN-MERCHANT")
        ok = await classify_transaction(session, t)
        assert ok is False
        assert t.needs_review == 1
        assert t.review_reason == "classification"


async def test_manual_classify_creates_candidate_rules(db, account_id, category_lookup):
    cat = category_lookup["Groceries"]
    async with db() as session:
        await _make_txn(session, account_id=account_id, narration="UPI-BIGBASKET-OKICI-9-")
        await session.commit()

    async with db() as session:
        t = (await session.execute(select(Transaction).limit(1))).scalar_one()
        await manual_classify(session, t, cat)

    async with db() as session:
        rules = (await session.execute(select(Rule))).scalars().all()
        assert len(rules) > 0
        assert all(r.status == "candidate" for r in rules)
        assert all(r.created_by == "user" for r in rules)
        assert all(r.category_id == cat for r in rules)


async def test_promotion_after_5_hits(db, category_lookup):
    cat = category_lookup["Eating Out"]
    async with db() as session:
        session.add(
            Rule(
                pattern="MCDONALD",
                pattern_type="token",
                category_id=cat,
                status="candidate",
                priority=100,
                created_by="user",
                hit_count=5,
                conflict_count=0,
            )
        )
        await session.commit()

    async with db() as session:
        promoted = await promote_eligible_candidates(session)
        assert promoted == 1

    async with db() as session:
        r = (await session.execute(select(Rule))).scalar_one()
        assert r.status == "active"
        assert r.promoted_at is not None


async def test_conflict_increments_on_user_override(db, account_id, category_lookup):
    cat_wrong = category_lookup["Groceries"]
    cat_right = category_lookup["Eating Out"]
    async with db() as session:
        session.add(
            Rule(
                pattern="MCDONALD",
                pattern_type="token",
                category_id=cat_wrong,
                status="active",
                priority=100,
                created_by="user",
            )
        )
        await session.flush()
        t = await _make_txn(session, account_id=account_id, narration="UPI-MCDONALDS-OK-1-")
        await classify_transaction(session, t)
        assert t.category_id == cat_wrong
        await session.commit()

    async with db() as session:
        t = (await session.execute(select(Transaction))).scalar_one()
        await manual_classify(session, t, cat_right)

    async with db() as session:
        r = (
            await session.execute(select(Rule).where(Rule.category_id == cat_wrong))
        ).scalar_one()
        assert r.conflict_count == 1


async def test_three_conflicts_disable_and_blacklist(db, account_id, category_lookup):
    cat_wrong = category_lookup["Groceries"]
    cat_right = category_lookup["Eating Out"]
    async with db() as session:
        session.add(
            Rule(
                pattern="MCDONALD",
                pattern_type="token",
                category_id=cat_wrong,
                status="active",
                priority=100,
                created_by="user",
                conflict_count=2,
            )
        )
        await session.flush()
        t = await _make_txn(session, account_id=account_id, narration="UPI-MCDONALDS-X-")
        await classify_transaction(session, t)
        await session.commit()

    async with db() as session:
        t = (await session.execute(select(Transaction))).scalar_one()
        await manual_classify(session, t, cat_right)

    async with db() as session:
        r = (
            await session.execute(select(Rule).where(Rule.category_id == cat_wrong))
        ).scalar_one()
        assert r.conflict_count == 3
        assert r.status == "disabled"
        assert r.blacklist_until is not None
