import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_active_storms_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/storms/active-swaths")
        assert res.status_code == 200
        data = res.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) > 0
        feature = data["features"][0]
        assert feature["geometry"]["type"] == "Polygon"
        assert feature["properties"]["max_hail_inches"] == 2.50
        assert feature["properties"]["kinetic_energy_joules"] > 0


@pytest.mark.asyncio
async def test_unresolved_exposure_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/intelligence/unresolved-exposure?min_sqft=50000")
        assert res.status_code == 200
        data = res.json()
        assert "total_targets" in data
        assert "targets" in data
        assert data["max_hail_inches"] == 2.50
        assert data["total_unresolved_valuation_mid"] > 0

        # Check target structure
        if data["targets"]:
            target = data["targets"][0]
            assert "parcelId" in target
            assert "buildingSqft" in target
            assert "kineticEnergyJoules" in target
            assert "estimatedReplacementFormatted" in target
            assert "unresolvedExposureScore" in target
            assert target["hasRepairPermit"] is False
