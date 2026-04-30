from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from api.main import create_app
from api.settings import get_settings


async def test_health_returns_ok(tmp_path, monkeypatch):
    db_path = tmp_path / "finassist.db"
    monkeypatch.setenv("FINASSIST_DB_PATH", str(db_path))
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    get_settings.cache_clear()


async def test_csv_exports_empty(tmp_path, monkeypatch):
    db_path = tmp_path / "finassist.db"
    monkeypatch.setenv("FINASSIST_DB_PATH", str(db_path))
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            for entity in ("transactions", "accounts"):
                r = await client.get(f"/exports/{entity}.csv")
                assert r.status_code == 200
                # Header row only — no data
                lines = [line for line in r.text.splitlines() if line.strip()]
                assert len(lines) == 1, f"{entity} should have only header, got: {r.text!r}"

            # Categories has seed data
            r = await client.get("/exports/categories.csv")
            assert r.status_code == 200
            lines = [line for line in r.text.splitlines() if line.strip()]
            assert len(lines) > 1
    get_settings.cache_clear()


async def test_export_unknown_entity_404(tmp_path, monkeypatch):
    db_path = tmp_path / "finassist.db"
    monkeypatch.setenv("FINASSIST_DB_PATH", str(db_path))
    get_settings.cache_clear()

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with app.router.lifespan_context(app):
            r = await client.get("/exports/bogus.csv")
            assert r.status_code == 404
    get_settings.cache_clear()
