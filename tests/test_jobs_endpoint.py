import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_trigger_job_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Without key -> 401
        res401 = await client.post("/api/v1/jobs/trigger-sync", json={"city_key": "dallas_tx"})
        assert res401.status_code == 401

        # With key -> 200
        headers = {"X-Depoii-Key": settings.API_KEY}
        res200 = await client.post("/api/v1/jobs/trigger-sync", json={"city_key": "dallas_tx"}, headers=headers)
        assert res200.status_code == 200
        data = res200.json()
        assert "job_id" in data
        assert data["city_key"] == "dallas_tx"
        assert "stream_url" in data


@pytest.mark.asyncio
async def test_stream_job_progress():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        headers = {"X-Depoii-Key": settings.API_KEY}
        res_trigger = await client.post("/api/v1/jobs/trigger-sync", json={"city_key": "dallas_tx"}, headers=headers)
        job_id = res_trigger.json()["job_id"]

        # Connect to stream
        stream_res = await client.get(f"/api/v1/jobs/{job_id}/stream")
        assert stream_res.status_code == 200
        assert "text/event-stream" in stream_res.headers["content-type"]
        text = stream_res.text
        assert "event: progress" in text
        assert "event: complete" in text
        assert "100" in text
