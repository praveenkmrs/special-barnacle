from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    accounts,
    analytics,
    categories,
    duplicates,
    envelopes,
    exports,
    health,
    holdings,
    imports as imports_route,
    rules,
    subscriptions,
    transactions,
    transfers,
)
from api.settings import get_settings
from core.investments.nav_fetcher import fetch_and_cache_nav
from db.init import initialize
from db.session import make_engine, make_session_factory

logger = logging.getLogger(__name__)


async def _scheduled_nav_fetch(session_factory) -> None:
    try:
        async with session_factory() as session:
            count = await fetch_and_cache_nav(session)
            logger.info("Scheduled NAV fetch upserted %d rows", count)
    except Exception:  # noqa: BLE001
        logger.exception("Scheduled NAV fetch failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await initialize(settings.db_path)

    engine = make_engine(settings.db_path)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    scheduler.add_job(
        _scheduled_nav_fetch,
        CronTrigger(hour=23, minute=30),
        kwargs={"session_factory": app.state.session_factory},
        id="amfi_nav_daily",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="FinAssist API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(exports.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(categories.router)
    app.include_router(imports_route.router)
    app.include_router(rules.router)
    app.include_router(duplicates.router)
    app.include_router(envelopes.router)
    app.include_router(transfers.router)
    app.include_router(subscriptions.router)
    app.include_router(holdings.router)
    app.include_router(analytics.router)

    return app


app = create_app()
