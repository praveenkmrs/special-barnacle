from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.banks.base import BankAdapter
from core.banks.registry import detect_bank, get_adapter_by_code
from core.imports.duplicate_detector import DupVerdict, check_duplicate
from core.parsing.raw_transaction import RawTransaction
from db.models import Import, Transaction


@dataclass
class ImportResult:
    import_id: int
    rows_imported: int
    rows_duplicate: int
    rows_ambiguous: int
    rows_failed: int
    period_start: str | None
    period_end: str | None
    status: str
    error_log: str | None = None


async def _persist_one(
    incoming: RawTransaction, account_id: int, session: AsyncSession
) -> tuple[str, int | None]:
    """Insert/skip incoming. Returns (outcome, new_id_or_None).

    outcome ∈ {"inserted_clean", "skipped_duplicate", "inserted_ambiguous"}.
    """
    result = await check_duplicate(incoming, account_id, session)

    if result.verdict is DupVerdict.DEFINITE_DUPLICATE:
        return "skipped_duplicate", None

    needs_review = result.verdict is DupVerdict.AMBIGUOUS
    review_reason = "duplicate" if needs_review else None

    txn = Transaction(
        account_id=account_id,
        txn_date=incoming.txn_date,
        amount=incoming.amount,
        type=incoming.type,
        narration=incoming.narration,
        narration_hash=incoming.narration_hash,
        balance_after=incoming.balance_after,
        reference=incoming.reference,
        value_date=incoming.value_date,
        is_transfer=0,
        classification_source="unclassified",
        needs_review=1 if needs_review else 0,
        review_reason=review_reason,
        source_file=incoming.source_file or None,
        source_page=incoming.source_page,
        source_line=incoming.source_line,
        raw_narration=incoming.raw_narration or None,
        raw_date_str=incoming.raw_date_str or None,
        raw_amount_str=incoming.raw_amount_str or None,
    )
    session.add(txn)
    await session.flush()  # populate txn.id

    if needs_review:
        # Allocate dup_group_id; reuse existing group if any of the matches are already grouped
        existing_groups = (
            await session.execute(
                select(Transaction.dup_group_id).where(
                    Transaction.id.in_(result.matched_existing_ids),
                    Transaction.dup_group_id.is_not(None),
                )
            )
        ).scalars().all()

        if existing_groups:
            group_id = existing_groups[0]
        else:
            max_group = (
                await session.execute(select(func.max(Transaction.dup_group_id)))
            ).scalar()
            group_id = (max_group or 0) + 1

        all_ids = list(result.matched_existing_ids) + [txn.id]
        await session.execute(
            update(Transaction)
            .where(Transaction.id.in_(all_ids))
            .values(
                dup_group_id=group_id,
                needs_review=1,
                review_reason="duplicate",
            )
        )
        return "inserted_ambiguous", txn.id

    return "inserted_clean", txn.id


async def import_statement(
    file_path: Path,
    account_id: int,
    session: AsyncSession,
    *,
    bank_code: str | None = None,
    password: str | None = None,
) -> ImportResult:
    """Detect bank, parse statement, persist transactions with dup detection."""
    adapter: BankAdapter | None
    if bank_code:
        adapter = get_adapter_by_code(bank_code)
    else:
        adapter = detect_bank(file_path)

    if adapter is None:
        return await _failed_import(
            session,
            file_path,
            account_id,
            bank_code,
            "Could not detect bank for this statement",
        )

    try:
        txns = adapter.parse(file_path, password=password, account_id=account_id)
    except Exception as e:  # noqa: BLE001
        return await _failed_import(session, file_path, account_id, adapter.bank_code, str(e))

    rows_imported = 0
    rows_duplicate = 0
    rows_ambiguous = 0
    rows_failed = 0
    errors: list[str] = []
    inserted_ids: list[int] = []

    for txn in txns:
        try:
            outcome, new_id = await _persist_one(txn, account_id, session)
            if outcome == "inserted_clean":
                rows_imported += 1
                if new_id is not None:
                    inserted_ids.append(new_id)
            elif outcome == "inserted_ambiguous":
                rows_imported += 1
                rows_ambiguous += 1
                if new_id is not None:
                    inserted_ids.append(new_id)
            elif outcome == "skipped_duplicate":
                rows_duplicate += 1
        except Exception as e:  # noqa: BLE001
            rows_failed += 1
            errors.append(f"line {txn.source_line}: {e}")

    # Auto-classify rows that aren't already in duplicate review
    from core.classifier.pipeline import classify_transaction

    for tid in inserted_ids:
        t = await session.get(Transaction, tid)
        if t is not None and t.review_reason != "duplicate":
            try:
                await classify_transaction(session, t)
            except Exception as e:  # noqa: BLE001
                errors.append(f"classify txn {tid}: {e}")

    period_start = min((t.txn_date for t in txns), default=None)
    period_end = max((t.txn_date for t in txns), default=None)

    status = "success"
    if rows_failed > 0 and rows_imported > 0:
        status = "partial"
    elif rows_failed > 0 and rows_imported == 0:
        status = "failed"

    suffix_to_format = {".pdf": "pdf", ".csv": "csv", ".tsv": "csv", ".xlsx": "xlsx"}
    src_format = suffix_to_format.get(file_path.suffix.lower(), "manual")

    imp = Import(
        account_id=account_id,
        source_file=file_path.name,
        source_format=src_format,
        bank_code=adapter.bank_code,
        period_start=period_start,
        period_end=period_end,
        rows_imported=rows_imported,
        rows_duplicate=rows_duplicate,
        rows_failed=rows_failed,
        status=status,
        error_log="\n".join(errors) if errors else None,
    )
    session.add(imp)
    await session.commit()
    await session.refresh(imp)

    return ImportResult(
        import_id=imp.id,
        rows_imported=rows_imported,
        rows_duplicate=rows_duplicate,
        rows_ambiguous=rows_ambiguous,
        rows_failed=rows_failed,
        period_start=period_start.isoformat() if period_start else None,
        period_end=period_end.isoformat() if period_end else None,
        status=status,
        error_log="\n".join(errors) if errors else None,
    )


async def _failed_import(
    session: AsyncSession,
    file_path: Path,
    account_id: int,
    bank_code: str | None,
    error: str,
) -> ImportResult:
    suffix_to_format = {".pdf": "pdf", ".csv": "csv", ".tsv": "csv", ".xlsx": "xlsx"}
    imp = Import(
        account_id=account_id,
        source_file=file_path.name,
        source_format=suffix_to_format.get(file_path.suffix.lower(), "manual"),
        bank_code=bank_code,
        rows_imported=0,
        rows_duplicate=0,
        rows_failed=0,
        status="failed",
        error_log=error,
    )
    session.add(imp)
    await session.commit()
    await session.refresh(imp)
    return ImportResult(
        import_id=imp.id,
        rows_imported=0,
        rows_duplicate=0,
        rows_ambiguous=0,
        rows_failed=0,
        period_start=None,
        period_end=None,
        status="failed",
        error_log=error,
    )
