from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.models import (
    Account,
    Category,
    Holding,
    HoldingTransaction,
    Import,
    NavCache,
    Rule,
    Subscription,
    Transaction,
)

router = APIRouter(prefix="/exports", tags=["exports"])


# Map exportable entity → (model class, column attribute names in CSV order)
EXPORTABLE: dict[str, tuple[type, list[str]]] = {
    "transactions": (
        Transaction,
        [
            "id",
            "account_id",
            "txn_date",
            "amount",
            "type",
            "narration",
            "narration_hash",
            "balance_after",
            "reference",
            "value_date",
            "category_id",
            "subscription_id",
            "transfer_pair_id",
            "is_transfer",
            "classification_source",
            "classification_confidence",
            "needs_review",
            "notes",
            "dup_group_id",
            "review_reason",
            "source_file",
            "source_page",
            "source_line",
            "raw_narration",
            "raw_date_str",
            "raw_amount_str",
            "imported_at",
        ],
    ),
    "accounts": (
        Account,
        [
            "id",
            "name",
            "type",
            "bank_code",
            "account_number_masked",
            "envelope_owner",
            "currency",
            "is_active",
            "opening_balance",
            "opening_balance_date",
            "created_at",
        ],
    ),
    "categories": (
        Category,
        ["id", "name", "parent_id", "is_transfer", "is_income", "display_order"],
    ),
    "rules": (
        Rule,
        [
            "id", "pattern", "pattern_type", "amount_min", "amount_max",
            "account_id", "txn_type", "category_id", "subscription_id",
            "status", "priority", "hit_count", "conflict_count",
            "last_hit_at", "created_by", "created_at", "promoted_at",
            "blacklist_until",
        ],
    ),
    "subscriptions": (
        Subscription,
        [
            "id", "name", "expected_amount", "amount_tolerance_pct", "cadence",
            "next_expected_date", "status", "category_id", "account_id",
            "started_on", "ended_on", "notes", "auto_detected",
        ],
    ),
    "holdings": (
        Holding,
        [
            "id", "account_id", "instrument_type", "identifier", "name",
            "units", "avg_cost", "total_invested", "current_nav",
            "current_value", "nav_updated_at",
        ],
    ),
    "holding_transactions": (
        HoldingTransaction,
        [
            "id", "holding_id", "txn_date", "type", "units", "price_per_unit",
            "amount", "linked_transaction_id", "notes",
        ],
    ),
    "imports": (
        Import,
        [
            "id", "account_id", "source_file", "source_format", "bank_code",
            "period_start", "period_end", "rows_imported", "rows_duplicate",
            "rows_failed", "status", "error_log", "imported_at",
        ],
    ),
    "nav_cache": (
        NavCache,
        ["id", "scheme_code", "scheme_name", "nav", "nav_date", "fetched_at"],
    ),
}


def _serialize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _stream_csv(model: type, columns: list[str], session: AsyncSession):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate()

    rows = (await session.execute(select(model))).scalars().all()
    for row in rows:
        writer.writerow([_serialize(getattr(row, col)) for col in columns])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()


@router.get("/{entity}.csv")
async def export_entity(
    entity: str,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if entity not in EXPORTABLE:
        raise HTTPException(404, f"Unknown export entity '{entity}'")
    model, columns = EXPORTABLE[entity]
    return StreamingResponse(
        _stream_csv(model, columns, session),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{entity}.csv"'},
    )
