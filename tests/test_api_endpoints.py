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
