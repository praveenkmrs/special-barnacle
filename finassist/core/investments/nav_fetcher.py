from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NavCache

AMFI_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
HEADER_TOKEN = "Scheme Code"


def parse_amfi_navall(text: str) -> list[dict[str, Any]]:
    """Parse AMFI NAVAll.txt content (pipe-delimited, but historically uses ';').

    Format: ``Scheme Code;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date``

    Skip header rows, blank rows, and section markers (lines without ``;`` or
    with fewer than 6 fields). Bad rows are skipped, never raised.
    """
    out: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if ";" not in line:
            # Section markers, fund-house headings, etc.
            continue
        parts = [p.strip() for p in line.split(";")]
        if len(parts) < 6:
            continue
        scheme_code = parts[0]
        scheme_name = parts[3]
        nav_str = parts[4]
        date_str = parts[5]

        if not scheme_code or not scheme_code[0].isdigit():
            # Header row ("Scheme Code...") or other non-data row.
            continue
        if scheme_code == HEADER_TOKEN:
            continue

        try:
            nav = Decimal(nav_str)
        except (InvalidOperation, ValueError):
            continue
        try:
            nav_date = datetime.strptime(date_str, "%d-%b-%Y").date()
        except ValueError:
            continue

        out.append(
            {
                "scheme_code": scheme_code,
                "scheme_name": scheme_name,
                "nav": nav,
                "nav_date": nav_date,
            }
        )
    return out


async def fetch_and_cache_nav(session: AsyncSession) -> int:
    """Fetch AMFI NAVAll.txt and upsert into nav_cache. Returns count upserted."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(AMFI_URL)
        resp.raise_for_status()
        text = resp.text

    rows = parse_amfi_navall(text)
    return await upsert_nav_rows(session, rows)


async def upsert_nav_rows(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> int:
    """Upsert parsed NAV rows. Returns count of rows written."""
    count = 0
    for row in rows:
        existing = (
            await session.execute(
                select(NavCache).where(
                    NavCache.scheme_code == row["scheme_code"],
                    NavCache.nav_date == row["nav_date"],
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                NavCache(
                    scheme_code=row["scheme_code"],
                    scheme_name=row["scheme_name"],
                    nav=row["nav"],
                    nav_date=row["nav_date"],
                )
            )
        else:
            existing.nav = row["nav"]
            existing.scheme_name = row["scheme_name"]
        count += 1
    await session.commit()
    return count


async def latest_nav_for_scheme(
    session: AsyncSession, scheme_code: str, on_or_before: date | None = None
) -> NavCache | None:
    stmt = select(NavCache).where(NavCache.scheme_code == scheme_code)
    if on_or_before is not None:
        stmt = stmt.where(NavCache.nav_date <= on_or_before)
    stmt = stmt.order_by(NavCache.nav_date.desc()).limit(1)
    return (await session.execute(stmt)).scalar_one_or_none()
