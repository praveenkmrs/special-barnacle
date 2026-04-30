from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.models import Account

router = APIRouter(prefix="/accounts", tags=["accounts"])


class AccountIn(BaseModel):
    name: str
    type: str = Field(pattern=r"^(bank|credit_card|cash_envelope|broker|mf|epf|nps)$")
    bank_code: str | None = None
    account_number_masked: str | None = None
    envelope_owner: str | None = None
    currency: str = "INR"
    opening_balance: Decimal = Decimal("0")
    opening_balance_date: date | None = None


class AccountOut(BaseModel):
    id: int
    name: str
    type: str
    bank_code: str | None
    account_number_masked: str | None
    envelope_owner: str | None
    currency: str
    is_active: int
    opening_balance: str
    opening_balance_date: date | None

    @classmethod
    def from_model(cls, m: Account) -> "AccountOut":
        return cls(
            id=m.id,
            name=m.name,
            type=m.type,
            bank_code=m.bank_code,
            account_number_masked=m.account_number_masked,
            envelope_owner=m.envelope_owner,
            currency=m.currency,
            is_active=m.is_active,
            opening_balance=str(m.opening_balance),
            opening_balance_date=m.opening_balance_date,
        )


@router.get("")
async def list_accounts(session: AsyncSession = Depends(get_session)) -> list[AccountOut]:
    rows = (await session.execute(select(Account).order_by(Account.name))).scalars().all()
    return [AccountOut.from_model(r) for r in rows]


@router.post("", status_code=201)
async def create_account(
    payload: AccountIn, session: AsyncSession = Depends(get_session)
) -> AccountOut:
    acct = Account(**payload.model_dump())
    session.add(acct)
    await session.commit()
    await session.refresh(acct)
    return AccountOut.from_model(acct)


@router.get("/{account_id}")
async def get_account(
    account_id: int, session: AsyncSession = Depends(get_session)
) -> AccountOut:
    acct = await session.get(Account, account_id)
    if acct is None:
        raise HTTPException(404, "Account not found")
    return AccountOut.from_model(acct)
