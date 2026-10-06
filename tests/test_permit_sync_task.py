import pytest
from app.tasks.permit_sync import run_permit_sync_task, _SYNC_HISTORY


@pytest.mark.asyncio
async def test_permit_sync_successful_ingestion():
    mock_records = [
        {
            "permit_number": "DAL-2026-001",
            "issued_date": "2026-03-01",
            "street_address": "500 COMMERCE ST",
            "contractor_name": "KPOST COMPANY",
            "estimated_cost": "1200000",
            "work_description": "COMMERCIAL TPO ROOF INSTALLATION",
            "status": "Issued",
        },
        {
            "permit_number": "DAL-2026-002",
            "issued_date": "2026-03-05",
            "street_address": "800 INDUSTRIAL BLVD",
            "contractor_name": "EMPIRE ROOFING",
            "estimated_cost": "850000",
            "work_description": "ROOF TEAR-OFF AND EPDM MEMBRANE",
            "status": "Issued",
        },
    ]

    res = await run_permit_sync_task("dallas_tx", mock_raw_data=mock_records)
    assert res.status in ("SUCCESS", "DRIFT_WARNING")
    assert res.records_fetched == 2
    assert res.records_normalized == 2
    assert len(res.normalized_permits) == 2


@pytest.mark.asyncio
async def test_zero_row_overwrite_protection():
    # Set up previous sync history for Dallas
    _SYNC_HISTORY["Dallas, TX"] = {
        "last_sync": "2026-10-05T00:00:00Z",
        "row_count": 140,
        "records_normalized": 140,
        "etag": "W/\"baseline-01\"",
    }

    # Now simulate a broken scraper returning 0 rows
    res = await run_permit_sync_task("dallas_tx", mock_raw_data=[])
    
    # Must be BLOCKED to protect production database!
    assert res.status == "ZERO_ROWS_BLOCKED"
    assert res.records_normalized == 0
    assert "Zero records returned" in (res.error_message or "")
