from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from core.investments.holdings_service import (
    InvestmentError,
    link_sip_transaction,
    refresh_all_holdings_value,
)
from core.investments.nav_fetcher import fetch_and_cache_nav
from db.models import Holding, HoldingTransaction

router = APIRouter(prefix="/holdings", tags=["holdings"])


def _dec_str(v: Decimal | None) -> str | None:
    return str(v) if v is not None else None


class HoldingIn(BaseModel):
    account_id: int
    instrument_type: str = Field(pattern=r"^(mf|stock|fd|epf|nps|crypto)$")
    identifier: str
    name: str


class HoldingOut(BaseModel):
    id: int
    account_id: int
    instrument_type: str
    identifier: str
    name: str
    units: str
    avg_cost: str | None
    total_invested: str
    current_nav: str | None
    current_value: str | None
    nav_updated_at: datetime | None
    gain: str | None
    gain_pct: float | None

    @classmethod
    def from_model(cls, h: Holding) -> "HoldingOut":
        invested = Decimal(h.total_invested or 0)
        cur_value = Decimal(h.current_value) if h.current_value is not None else None
        gain: Decimal | None = None
        gain_pct: float | None = None
        if cur_value is not None:
            gain = cur_value - invested
            if invested != 0:
                gain_pct = float(gain / invested * Decimal(100))
        return cls(
            id=h.id,
            account_id=h.account_id,
            instrument_type=h.instrument_type,
            identifier=h.identifier,
            name=h.name,
            units=str(h.units),
            avg_cost=_dec_str(h.avg_cost),
            total_invested=str(h.total_invested),
            current_nav=_dec_str(h.current_nav),
            current_value=_dec_str(h.current_value),
            nav_updated_at=h.nav_updated_at,
            gain=_dec_str(gain),
            gain_pct=gain_pct,
        )


class HoldingTxnOut(BaseModel):
    id: int
    holding_id: int
    txn_date: date
    type: str
    units: str
    price_per_unit: str | None
    amount: str
    linked_transaction_id: int | None
    notes: str | None

    @classmethod
    def from_model(cls, t: HoldingTransaction) -> "HoldingTxnOut":
        return cls(
            id=t.id,
            holding_id=t.holding_id,
            txn_date=t.txn_date,
            type=t.type,
            units=str(t.units),
            price_per_unit=_dec_str(t.price_per_unit),
            amount=str(t.amount),
            linked_transaction_id=t.linked_transaction_id,
            notes=t.notes,
        )


class RefreshResult(BaseModel):
    nav_rows_updated: int
    holdings_revalued: int


class LinkSipIn(BaseModel):
    transaction_id: int


@router.get("")
async def list_holdings(session: AsyncSession = Depends(get_session)) -> list[HoldingOut]:
    rows = (
        await session.execute(select(Holding).order_by(Holding.name))
    ).scalars().all()
    return [HoldingOut.from_model(r) for r in rows]


@router.post("", status_code=201)
async def create_holding(
    payload: HoldingIn, session: AsyncSession = Depends(get_session)
) -> HoldingOut:
    h = Holding(
        account_id=payload.account_id,
        instrument_type=payload.instrument_type,
        identifier=payload.identifier,
        name=payload.name,
    )
    session.add(h)
    await session.commit()
    await session.refresh(h)
    return HoldingOut.from_model(h)


@router.post("/refresh-nav")
async def refresh_nav(session: AsyncSession = Depends(get_session)) -> RefreshResult:
    try:
        nav_count = await fetch_and_cache_nav(session)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"NAV fetch failed: {e}") from e
    revalued = await refresh_all_holdings_value(session)
    return RefreshResult(nav_rows_updated=nav_count, holdings_revalued=revalued)


@router.get("/{holding_id}/transactions")
async def list_holding_transactions(
    holding_id: int, session: AsyncSession = Depends(get_session)
) -> list[HoldingTxnOut]:
    rows = (
        await session.execute(
            select(HoldingTransaction)
            .where(HoldingTransaction.holding_id == holding_id)
            .order_by(HoldingTransaction.txn_date.desc(), HoldingTransaction.id.desc())
        )
    ).scalars().all()
    return [HoldingTxnOut.from_model(r) for r in rows]


@router.post("/{holding_id}/link-sip")
async def link_sip(
    holding_id: int,
    payload: LinkSipIn,
    session: AsyncSession = Depends(get_session),
) -> HoldingTxnOut:
    try:
        ht = await link_sip_transaction(payload.transaction_id, holding_id, session)
    except InvestmentError as e:
        raise HTTPException(400, str(e)) from e
    return HoldingTxnOut.from_model(ht)
