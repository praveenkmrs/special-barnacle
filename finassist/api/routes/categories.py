from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from db.models import Category

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    is_transfer: int
    is_income: int
    display_order: int | None

    @classmethod
    def from_model(cls, c: Category) -> "CategoryOut":
        return cls(
            id=c.id,
            name=c.name,
            parent_id=c.parent_id,
            is_transfer=c.is_transfer,
            is_income=c.is_income,
            display_order=c.display_order,
        )


class CategoryIn(BaseModel):
    name: str
    parent_id: int | None = None
    is_transfer: int = 0
    is_income: int = 0
    display_order: int | None = 100


@router.get("")
async def list_categories(session: AsyncSession = Depends(get_session)) -> list[CategoryOut]:
    rows = (
        await session.execute(
            select(Category).order_by(
                Category.parent_id.is_(None).desc(),
                Category.display_order,
                Category.name,
            )
        )
    ).scalars().all()
    return [CategoryOut.from_model(r) for r in rows]


@router.post("", status_code=201)
async def create_category(
    payload: CategoryIn, session: AsyncSession = Depends(get_session)
) -> CategoryOut:
    c = Category(**payload.model_dump())
    session.add(c)
    await session.commit()
    await session.refresh(c)
    return CategoryOut.from_model(c)
