from __future__ import annotations

import shutil
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.imports.service import import_statement
from core.parsing.decryptor import PDFPasswordIncorrect, PDFPasswordRequired
from db.models import Import

router = APIRouter(prefix="/imports", tags=["imports"])


class ImportOut(BaseModel):
    id: int
    account_id: int
    source_file: str | None
    source_format: str | None
    bank_code: str | None
    period_start: date | None
    period_end: date | None
    rows_imported: int
    rows_duplicate: int
    rows_failed: int
    status: str | None
    error_log: str | None

    @classmethod
    def from_model(cls, m: Import) -> "ImportOut":
        return cls(
            id=m.id,
            account_id=m.account_id,
            source_file=m.source_file,
            source_format=m.source_format,
            bank_code=m.bank_code,
            period_start=m.period_start,
            period_end=m.period_end,
            rows_imported=m.rows_imported,
            rows_duplicate=m.rows_duplicate,
            rows_failed=m.rows_failed,
            status=m.status,
            error_log=m.error_log,
        )


class ImportResultOut(BaseModel):
    import_id: int
    rows_imported: int
    rows_duplicate: int
    rows_ambiguous: int
    rows_failed: int
    period_start: str | None
    period_end: str | None
    status: str
    error_log: str | None


@router.get("")
async def list_imports(session: AsyncSession = Depends(get_session)) -> list[ImportOut]:
    rows = (
        await session.execute(select(Import).order_by(Import.imported_at.desc()))
    ).scalars().all()
    return [ImportOut.from_model(r) for r in rows]


@router.post("", status_code=201)
async def create_import(
    account_id: int = Form(...),
    bank_code: str | None = Form(default=None),
    password: str | None = Form(default=None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> ImportResultOut:
    if not file.filename:
        raise HTTPException(400, "file is required")

    suffix = Path(file.filename).suffix.lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = await import_statement(
            tmp_path,
            account_id,
            session,
            bank_code=bank_code,
            password=password,
        )
    except PDFPasswordRequired as e:
        raise HTTPException(401, f"Password required: {e}") from e
    except PDFPasswordIncorrect as e:
        raise HTTPException(403, f"Incorrect password: {e}") from e
    finally:
        tmp_path.unlink(missing_ok=True)

    # Restore filename in the import record so the user sees their original name
    if result.import_id:
        imp = await session.get(Import, result.import_id)
        if imp is not None and imp.source_file != file.filename:
            imp.source_file = file.filename
            await session.commit()

    return ImportResultOut(
        import_id=result.import_id,
        rows_imported=result.rows_imported,
        rows_duplicate=result.rows_duplicate,
        rows_ambiguous=result.rows_ambiguous,
        rows_failed=result.rows_failed,
        period_start=result.period_start,
        period_end=result.period_end,
        status=result.status,
        error_log=result.error_log,
    )
