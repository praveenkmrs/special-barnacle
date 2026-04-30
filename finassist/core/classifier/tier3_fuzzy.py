from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Transaction

THRESHOLD = 0.85


@dataclass
class FuzzyMatch:
    category_id: int | None
    confidence: float
    suggestions: list[tuple[int, float]]  # top-3 (category_id, score)


async def fuzzy_classify(session: AsyncSession, txn: Transaction) -> FuzzyMatch | None:
    """TF-IDF cosine similarity over manually-classified narrations."""
    # Only consider human-classified rows; otherwise we'd amplify earlier mistakes.
    rows = (
        await session.execute(
            select(Transaction.narration, Transaction.category_id).where(
                Transaction.classification_source == "manual",
                Transaction.category_id.is_not(None),
            )
        )
    ).all()

    if not rows:
        return None

    corpus = [r[0] for r in rows] + [txn.narration]
    cat_ids = [r[1] for r in rows]

    # Lazy import — sklearn is heavy
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        max_df=1.0,
        lowercase=True,
    )
    matrix = vectorizer.fit_transform(corpus)
    sims = cosine_similarity(matrix[-1], matrix[:-1]).flatten()

    # Aggregate similarity by category — top-N per category, mean
    from collections import defaultdict

    cat_sims: dict[int, list[float]] = defaultdict(list)
    for cat_id, sim in zip(cat_ids, sims, strict=False):
        if cat_id is not None:
            cat_sims[cat_id].append(float(sim))

    aggregated = sorted(
        ((cid, max(scores)) for cid, scores in cat_sims.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    if not aggregated:
        return None

    top_three = aggregated[:3]
    best_cat, best_score = top_three[0]
    if best_score >= THRESHOLD:
        return FuzzyMatch(
            category_id=best_cat,
            confidence=best_score,
            suggestions=top_three,
        )
    return FuzzyMatch(category_id=None, confidence=best_score, suggestions=top_three)
