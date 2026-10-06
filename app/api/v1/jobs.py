import asyncio
import json
import uuid
from typing import Dict, Any, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.security import verify_api_key
from app.extraction.config_loader import list_configured_cities
from app.tasks.permit_sync import run_permit_sync_task
from app.api.v1.permits import _PERMIT_WAREHOUSE

router = APIRouter(prefix="/jobs", tags=["Background Jobs & SSE Streaming"])

# In-memory registry of active streaming jobs
_ACTIVE_JOBS: Dict[str, Dict[str, Any]] = {}


class TriggerSyncRequest(BaseModel):
    city_key: str


class TriggerSyncResponse(BaseModel):
    job_id: str
    city_key: str
    status: str
    stream_url: str


@router.post("/trigger-sync", response_model=TriggerSyncResponse, dependencies=[Depends(verify_api_key)])
async def trigger_sync_job(payload: TriggerSyncRequest) -> TriggerSyncResponse:
    """
    Asynchronously triggers a municipal scraper job and creates an SSE stream session.
    """
    configured = list_configured_cities()
    if payload.city_key not in configured:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City '{payload.city_key}' is not configured. Available: {configured}",
        )

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    _ACTIVE_JOBS[job_id] = {
        "city_key": payload.city_key,
        "status": "QUEUED",
        "progress_pct": 0,
        "messages": ["Job queued in Depoii Data Engine"],
    }

    return TriggerSyncResponse(
        job_id=job_id,
        city_key=payload.city_key,
        status="QUEUED",
        stream_url=f"/api/v1/jobs/{job_id}/stream",
    )


async def sse_event_stream(job_id: str) -> AsyncGenerator[str, None]:
    """
    Generates Server-Sent Events (SSE) streaming live ingestion progress to the Next.js UI.
    """
    job_info = _ACTIVE_JOBS.get(job_id)
    if not job_info:
        yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
        return

    city_key = job_info["city_key"]

    # Step 1: Connecting
    yield f"event: progress\ndata: {json.dumps({'pct': 15, 'step': 'CONNECTING', 'message': f'Establishing session with {city_key} portal...'})}\n\n"
    await asyncio.sleep(0.3)

    # Step 2: Fetching
    yield f"event: progress\ndata: {json.dumps({'pct': 40, 'step': 'EXTRACTING', 'message': 'Ingesting municipal permit records and raw payloads...'})}\n\n"
    
    # Run sync task
    result = await run_permit_sync_task(city_key)

    # Update in-memory warehouse
    for permit in result.normalized_permits:
        _PERMIT_WAREHOUSE[permit.id] = permit

    # Step 3: Normalizing & Science
    yield f"event: progress\ndata: {json.dumps({'pct': 75, 'step': 'NORMALIZING', 'message': 'Running RapidFuzz contractor resolution and membrane NLP pipeline...'})}\n\n"
    await asyncio.sleep(0.3)

    # Step 4: Complete
    complete_payload = {
        "pct": 100,
        "step": "COMPLETE",
        "status": result.status,
        "jurisdiction": result.jurisdiction,
        "records_fetched": result.records_fetched,
        "records_normalized": result.records_normalized,
        "duplicates_removed": result.duplicates_removed,
        "duration_seconds": result.duration_seconds,
    }
    yield f"event: complete\ndata: {json.dumps(complete_payload)}\n\n"

    # Clean up job after streaming finishes
    if job_id in _ACTIVE_JOBS:
        _ACTIVE_JOBS[job_id]["status"] = "COMPLETED"


@router.get("/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """
    Server-Sent Events (SSE) stream endpoint for live real-time ingestion progress.
    """
    return StreamingResponse(
        sse_event_stream(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
