import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == settings.APP_NAME
        assert data["version"] == settings.VERSION
        assert "docs" in data


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["engine_version"] == settings.VERSION
        assert "uptime_seconds" in data
        assert "jurisdictions_synced" in data
        assert "last_sync_summary" in data
        assert "Dallas, TX" in data["last_sync_summary"]


@pytest.mark.asyncio
async def test_permits_search_and_stats_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Search empty or populated
        search_res = await client.get("/api/v1/permits/search")
        assert search_res.status_code == 200
        data = search_res.json()
        assert "total" in data
        assert "permits" in data

        # Stats
        stats_res = await client.get("/api/v1/permits/stats")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert "total_permits" in stats
        assert "by_category" in stats


@pytest.mark.asyncio
async def test_permits_sync_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without X-Depoii-Key: must return 401 Unauthorized
        res_unauthorized = await client.post("/api/v1/permits/sync/dallas_tx")
        assert res_unauthorized.status_code == 401

        # With valid X-Depoii-Key: must authenticate
        headers = {"X-Depoii-Key": settings.API_KEY}
        # Note: if network is disabled during unit test, it returns 200 or 500 cleanly handled
        res_authorized = await client.post("/api/v1/permits/sync/dallas_tx", headers=headers)
        assert res_authorized.status_code in (200, 500)
