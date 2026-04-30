from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from db.seeds import seed_default_categories
from db.session import make_engine, make_session_factory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"


def run_migrations(db_path: Path) -> None:
    """Apply Alembic migrations against `db_path` (sync — uses Alembic CLI machinery)."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")
    command.upgrade(cfg, "head")


async def initialize(db_path: Path) -> int:
    """Apply migrations and seed defaults. Returns count of newly seeded rows."""
    run_migrations(db_path)

    engine = make_engine(db_path)
    factory = make_session_factory(engine)
    try:
        async with factory() as session:
            return await seed_default_categories(session)
    finally:
        await engine.dispose()
