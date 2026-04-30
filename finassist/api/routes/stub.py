"""Empty route shells for Phase 1 — replaced as each phase fills them in."""
from __future__ import annotations

from fastapi import APIRouter


def make_stub_router(prefix: str, tag: str) -> APIRouter:
    router = APIRouter(prefix=f"/{prefix}", tags=[tag])

    @router.get("")
    async def list_items() -> list[dict]:
        return []

    return router


holdings_router = make_stub_router("holdings", "holdings")
analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_router.get("/dashboard")
async def dashboard_stub() -> dict:
    return {
        "cash_buffer": "0",
        "capital_deployed": "0",
        "net_cashflow": "0",
        "accounts": [],
        "categories": [],
        "subscriptions": [],
    }
