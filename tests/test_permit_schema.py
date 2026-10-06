import json
import pytest
from app.schemas.permit_schema import DepoiiNormalizedPermitSchema, NormalizationBatchResultSchema


def test_normalized_permit_schema_serialization():
    data = {
        "id": "DEP-TX-DAL-COM-ROOF-26-000300",
        "sourceSystem": "socrata",
        "rawPermitNumber": "2601141002",
        "jurisdiction": "Dallas, TX",
        "state": "TX",
        "county": "Dallas County",
        "issueDate": "2026-02-18",
        "status": "Issued",
        "normalizedAddress": "1200 N STEMMONS FWY",
        "city": "Dallas",
        "zipCode": "75207",
        "valuation": 1850000.0,
        "valuationFormatted": "$1.85M",
        "category": "Commercial Re-Roof",
        "rawDescription": "REPLACE EXISTING ROOF SYSTEM WITH 60-MIL TPO",
        "probableRoofSystem": "TPO Single-Ply",
        "contractorName": "KPOST COMPANY",
        "isHailStormWindow": True,
        "isCompetitorCapture": True,
        "confidenceScore": 95,
        "normalizedAt": "2026-10-06T12:00:00Z"
    }

    # Validate against Pydantic schema using alias population
    model = DepoiiNormalizedPermitSchema.model_validate(data)
    assert model.id == "DEP-TX-DAL-COM-ROOF-26-000300"
    assert model.source_system == "socrata"
    assert model.valuation == 1850000.0
    assert model.contractor_name == "KPOST COMPANY"

    # Export using camelCase aliases (by_alias=True) to match Next.js expectation
    dumped = model.model_dump(by_alias=True)
    assert dumped["sourceSystem"] == "socrata"
    assert dumped["rawPermitNumber"] == "2601141002"
    assert dumped["normalizedAddress"] == "1200 N STEMMONS FWY"
    assert dumped["isCompetitorCapture"] is True
