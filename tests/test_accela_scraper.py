import pytest
from app.extraction.config_loader import load_city_config
from app.extraction.accela_scraper import parse_accela_html_table, UniversalAccelaScraper
from app.science.normalizer import normalize_accela_permit
from app.tasks.permit_sync import run_permit_sync_task


MOCK_ACCELA_HTML = """
<html>
<body>
    <table id="ctl00_PlaceHolderMain_gdvPermitList" class="ACA_GridView">
        <tr class="ACA_Header">
            <th>Action</th>
            <th>Record Number</th>
            <th>Record Type</th>
            <th>Address</th>
            <th>Date</th>
            <th>Status</th>
        </tr>
        <tr>
            <td><a href="#">View</a></td>
            <td>PB24-09821</td>
            <td>Commercial Re-Roof</td>
            <td>7800 ALLIANCE GATEWAY FWY</td>
            <td>07/03/2024</td>
            <td>Issued</td>
        </tr>
        <tr>
            <td><a href="#">View</a></td>
            <td>PB24-11402</td>
            <td>Commercial Waterproofing & Coating</td>
            <td>1500 MERCANTILE DR</td>
            <td>07/15/2024</td>
            <td>Active</td>
        </tr>
    </table>
</body>
</html>
"""


def test_parse_accela_html_table():
    config = load_city_config("fort_worth_tx")
    records = parse_accela_html_table(MOCK_ACCELA_HTML, config)

    assert len(records) == 2
    rec1 = records[0]
    assert rec1["permit_number"] == "PB24-09821"
    assert rec1["record_type"] == "Commercial Re-Roof"
    assert rec1["address"] == "7800 ALLIANCE GATEWAY FWY"
    assert rec1["issue_date"] == "07/03/2024"
    assert rec1["status"] == "Issued"
    assert rec1["jurisdiction"] == "Fort Worth, TX"


def test_normalize_accela_permit():
    raw = {
        "permit_number": "PB24-09821",
        "issue_date": "07/03/2024",
        "address": "7800 ALLIANCE GATEWAY FWY",
        "contractor": "CENTIMARK CORPORATION (RCAT #8812)",
        "job_value": "4200000",
        "record_type": "Commercial Re-Roof",
        "description": "Complete roof tear off 320,000 sq ft logistics hub. Install 80-mil TPO membrane.",
        "status": "Issued",
    }

    norm = normalize_accela_permit(raw, jurisdiction="Fort Worth, TX", state="TX")

    assert norm.id == "DEP-TX-ACA-PB24-09821"
    assert norm.source_system == "accela"
    assert norm.raw_permit_number == "PB24-09821"
    assert norm.jurisdiction == "Fort Worth, TX"
    assert norm.valuation == 4200000.0
    assert norm.valuation_formatted == "$4.20M"
    assert norm.category == "Roof Tear-Off & Replace"
    assert norm.probable_roof_system == "TPO Single-Ply"
    assert norm.square_footage == 320000
    assert norm.contractor_name == "Centimark Corporation"
    assert norm.contractor_license == "8812"
    assert norm.is_competitor_capture is True


def test_tier2_city_configs():
    tampa = load_city_config("tampa_fl")
    assert tampa.jurisdiction == "Tampa, FL"
    assert tampa.platform == "accela"
    assert tampa.portal is not None
    assert "tampagov.net" in tampa.portal.base_url

    okc = load_city_config("oklahoma_city_ok")
    assert okc.jurisdiction == "Oklahoma City, OK"
    assert okc.platform == "accela"
    assert okc.portal is not None
    assert "okc.gov" in okc.portal.base_url


@pytest.mark.asyncio
async def test_accela_sync_pipeline():
    mock_records = [
        {
            "permit_number": "PB24-09821",
            "issue_date": "07/03/2024",
            "address": "7800 ALLIANCE GATEWAY FWY",
            "contractor": "CENTIMARK CORPORATION",
            "job_value": "4200000",
            "record_type": "Commercial Re-Roof",
            "description": "Commercial TPO roof installation",
            "status": "Issued",
        }
    ]

    res = await run_permit_sync_task("fort_worth_tx", mock_raw_data=mock_records)
    assert res.status in ("SUCCESS", "DRIFT_WARNING")
    assert res.source_system == "accela"
    assert res.records_fetched == 1
    assert res.records_normalized == 1
    assert res.normalized_permits[0].source_system == "accela"
    assert res.normalized_permits[0].valuation == 4200000.0
