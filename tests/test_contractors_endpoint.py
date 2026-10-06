import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_contractor_leaderboard_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/contractors/leaderboard")
        assert res.status_code == 200
        data = res.json()
        assert "total_contractors" in data
        assert "total_industry_valuation_usd" in data
        assert "leaderboard" in data
        assert len(data["leaderboard"]) > 0

        first = data["leaderboard"][0]
        assert "canonicalId" in first
        assert "canonicalName" in first
        assert "totalValuationUSD" in first
        assert "totalValuationFormatted" in first
        assert "marketSharePct" in first
        assert "primaryRoofSystem" in first
        assert "aliases" in first
