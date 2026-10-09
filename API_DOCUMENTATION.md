# Roofx / Depoii Data Engine — FastAPI API Reference Specification

**Base URLs:**
- Local Development: `http://127.0.0.1:8001` or `http://localhost:8001`
- Interactive OpenAPI / Swagger UI: `http://127.0.0.1:8001/docs`
- ReDoc Documentation: `http://127.0.0.1:8001/redoc`
- OpenAPI JSON Schema: `http://127.0.0.1:8001/openapi.json`

---

## 1. System Overview & Architecture

The **Roofx / Depoii Data Engine** is an autonomous commercial intelligence engine built on **FastAPI**, **SQLite** (with spatial indices and GIS point-in-polygon matching), and **Pydantic v2**.

It continuously cleans, normalizes, and connects 4 disparate datasets:
1. **Municipal Commercial Building Permits** (21,370+ records across NYC, Seattle, Dallas, Fort Worth, Gainesville, Cincinnati).
2. **County Tax Assessor & GIS Parcels** (Deed owners, commercial square footage, year built, land use codes).
3. **NOAA Severe Weather & Storm Swaths** (Hail size >1.0", wind vectors, radar swath polygons).
4. **Contractor Entity Profiles** (Canonical license holders, win-shares, membrane specialization).

---

## 2. Global Headers & Conventions

| Header | Type | Description |
| :--- | :--- | :--- |
| `X-Correlation-ID` | String (Optional) | Client-provided or auto-generated UUID for tracing requests across logs. Echoed back in response headers. |
| `X-Depoii-Key` | String (Required for mutations) | Authentication key required for triggering background syncs (`POST /api/v1/jobs/trigger-sync`). Default local key: `roofx-dev-secret-key`. |
| `Content-Type` | String | `application/json` (or `text/event-stream` for SSE streaming). |

---

## 3. API Directory & Detailed Endpoint Reference

### Module 1: Root & Health Observability

#### `GET /` — Root Service Info
* **Purpose & Use Case:** Quick connectivity test; returns system version, active environment, and links to documentation.
* **Request:** No parameters or body.
* **Response (200 OK):**
```json
{
  "service": "Depoii Data Engine",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs",
  "health": "/health",
  "metrics": "/metrics"
}
```

#### `GET /health` or `GET /api/v1/health` — System Health Probe
* **Purpose & Use Case:** Liveness and readiness probe for Docker/Kubernetes and frontend monitoring. Verifies database connectivity and record totals.
* **Request:** No parameters or body.
* **Response (200 OK):**
```json
{
  "status": "healthy",
  "environment": "development",
  "database": {
    "status": "connected",
    "total_permits": 21372,
    "total_contractors": 2092,
    "total_storms": 20
  },
  "timestamp": "2026-10-08T05:00:00Z"
}
```

#### `GET /metrics` — Prometheus OpenMetrics
* **Purpose & Use Case:** Prometheus / Datadog scraping endpoint returning request rates, query latencies, and active connection counts.
* **Content-Type:** `text/plain; version=0.0.4; charset=utf-8`

---

### Module 2: Commercial Permits Engine

#### `GET /api/v1/permits/search` — High-Performance Permit Search & Filter
* **Purpose & Use Case:** The primary workhorse API powering the Roofx **All Permits Command Center** table. Allows multi-attribute filtering by geography, valuation, roof system (TPO, EPDM, Built-Up, Metal), contractor, and intelligence status.
* **Query Parameters:**
  * `jurisdiction` *(string, optional)*: Filter by municipality (e.g. `nyc_dob`, `seattle_sdci`, `dallas_tx`, `fort_worth_tx`).
  * `state` *(string, optional)*: 2-letter state code (`NY`, `WA`, `TX`, `OH`, `FL`).
  * `city` *(string, optional)*: Exact city name (e.g. `Dallas`, `Seattle`, `New York`).
  * `contractor` *(string, optional)*: Fuzzy or exact contractor name.
  * `category` *(string, optional)*: Filter by permit type (e.g. `REROOF`, `NEW_CONSTRUCTION`, `ALTERATION`).
  * `probable_roof_system` *(string, optional)*: Detected roof membrane (e.g. `TPO`, `EPDM`, `MODIFIED_BITUMEN`, `METAL`, `BUILT_UP`, `BUR`).
  * `status_filter` *(string, optional)*: Status filter: `active` (Issued/In Review), `completed` (Finaled/Closed), `expired`.
  * `intelligence_mode` *(string, optional)*: Specialized view: `all`, `storm_matched`, `unresolved_hail`, `commercial_only`.
  * `min_valuation` *(float, optional)*: Minimum project job valuation in USD (e.g. `50000`).
  * `max_valuation` *(float, optional)*: Maximum project valuation in USD.
  * `is_hail_storm_window` *(boolean, optional)*: Filter for permits filed within 180 days of an active storm swath.
  * `search` *(string, optional)*: Full-text search matching permit number, address, contractor, or scope description.
  * `sort_by` *(string, optional, default: `date_desc`)*: `date_desc`, `date_asc`, `valuation_desc`, `valuation_asc`.
  * `limit` *(int, default: 50, max: 200)*: Pagination page size.
  * `offset` *(int, default: 0)*: Pagination offset.
* **Response (200 OK):**
```json
{
  "total": 21372,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": "perm_982341",
      "permit_number": "PR-2024-009182",
      "jurisdiction": "dallas_tx",
      "address": "2100 ROSS AVE, DALLAS, TX 75201",
      "city": "Dallas",
      "state": "TX",
      "postal_code": "75201",
      "issue_date": "2024-06-14",
      "status": "ISSUED",
      "valuation": 485000.0,
      "probable_roof_system": "TPO",
      "contractor_name": "CENTIMARK CORPORATION",
      "contractor_id": "cont_4812",
      "description": "COMMERCIAL REROOF: REMOVE EXISTING MEMBRANE AND INSTALL 60 MIL TPO ROOFING SYSTEM OVER 2.0 INCH POLYISO INSULATION",
      "square_footage": 62500,
      "is_hail_storm_window": true,
      "parcel_id": "dfw_cad_001928"
    }
  ]
}
```

#### `GET /api/v1/permits/active-jobsites` — Active Jobsite Tracker
* **Purpose & Use Case:** Feeds the **Active Jobsites** page. Surfaces commercial roofs currently under active construction, crane presence, or pending final inspection within the last 90–180 days.
* **Query Parameters:**
  * `jurisdiction` *(string, optional)*
  * `contractor` *(string, optional)*
  * `roof_system` *(string, optional)*
  * `min_valuation` *(float, optional)*
  * `search` *(string, optional)*
  * `limit` *(int, default: 50)*
  * `offset` *(int, default: 0)*
* **Response (200 OK):** Returns items with active job flags, estimated completion dates, and days elapsed since permit issuance.

#### `GET /api/v1/permits/roof-aging-alarm` — Roof Aging & Replacement Predictor
* **Purpose & Use Case:** Identifies buildings where the last permitted roof was installed **15 to 25+ years ago**, calculating failure probabilities and replacement timelines.
* **Query Parameters:**
  * `jurisdiction` *(string, optional)*
  * `risk_tier` *(string, optional)*: `CRITICAL` (20+ yrs), `HIGH` (15-19 yrs), `MODERATE` (10-14 yrs).
  * `min_age` *(int, optional, default: 15)*: Filter for roof installations older than N years.
  * `min_valuation` *(float, optional)*
  * `search` *(string, optional)*
  * `limit` *(int, default: 50)*
  * `offset` *(int, default: 0)*
* **Response (200 OK):**
```json
{
  "total": 1284,
  "items": [
    {
      "id": "perm_00192",
      "address": "450 7TH AVE, NEW YORK, NY 10123",
      "last_permit_date": "2006-03-12",
      "roof_age_years": 18,
      "risk_tier": "HIGH",
      "probable_roof_system": "BUILT_UP",
      "deed_owner": "NELSON TOWER VENTURES LLC",
      "estimated_replacement_cost": 320000.0
    }
  ]
}
```

#### `GET /api/v1/permits/multiphase-projects` — Multi-Phase / Campus Projects
* **Purpose & Use Case:** Clusters permits belonging to multi-building corporate campuses, business parks, or multi-story phased reroofs where one permit indicates future pipeline phases.
* **Query Parameters:**
  * `jurisdiction` *(string, optional)*
  * `min_phases` *(int, default: 2)*: Minimum permits clustered on the same parcel/campus.
  * `min_valuation` *(float, optional)*
  * `status_filter` *(string, optional)*
  * `search` *(string, optional)*
  * `limit` *(int, default: 50)*
  * `offset` *(int, default: 0)*

#### `GET /api/v1/permits/stats` — High-Level KPI Aggregations
* **Purpose & Use Case:** Top-level metrics for dashboard cards (total permits, pipeline valuation in billions, active jobsites, storm-hit roofs).
* **Response (200 OK):**
```json
{
  "total_permits": 21372,
  "active_jobsites": 3412,
  "aging_alarms": 1284,
  "total_pipeline_valuation": 842190000.0,
  "top_membrane": "TPO",
  "active_contractors_count": 2092
}
```

#### `GET /api/v1/permits/cities` — Unique Cities Directory
* **Purpose & Use Case:** Returns distinct cities and states available in the normalized permits table for populating search dropdowns.

#### `GET /api/v1/permits/parcels/{parcel_id}` — Parcel Permit Dossier
* **Purpose & Use Case:** Fetches the complete permit history and structural profile for a specific parcel ID.

#### `POST /api/v1/permits/sync/{city_key}` — Ingest & Sync Municipality
* **Purpose & Use Case:** Triggers real-time municipal scraper/API ingest for a target city (e.g. `dallas_tx`, `nyc_dob`).
* **Path Parameters:**
  * `city_key`: `dallas_tx`, `fort_worth_tx`, `seattle_sdci`, `nyc_dob`.

---

### Module 3: Commercial Property Parcels & "Dark Market" Engine

#### `GET /api/v1/parcels/dark-market/overdue` — The "Dark Market" Engine
* **Purpose & Use Case:** **Core Moat API.** Identifies high-value commercial parcels built between 15 and 60+ years ago that have **zero municipal roofing permits on record**. These represent roofs past their useful lifespan whose owners have never been pitched by reroof contractors.
* **Query Parameters:**
  * `min_age` *(int, default: 15)*: Minimum building age (e.g. 15, 20, 25 years).
  * `min_sqft` *(int, default: 25000)*: Minimum commercial footprint in sq ft (filters out residential/small shops).
  * `limit` *(int, default: 50, max: 200)*
  * `offset` *(int, default: 0)*
* **Response (200 OK):**
```json
{
  "total": 673,
  "min_age": 15,
  "min_sqft": 25000,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "parcel_id": "nyc_pluto_1008010001",
      "address": "350 5TH AVE",
      "city": "New York",
      "state": "NY",
      "county": "New York",
      "owner_name": "ESRT EMPIRE STATE BUILDING LLC",
      "year_built": 1931,
      "building_age_years": 93,
      "bldg_sqft": 2812000,
      "land_use": "Commercial Office",
      "permit_count": 0,
      "est_roof_replacement_cost": 4218000.0,
      "overdue_category": "OVERDUE (30+ YRS)"
    }
  ]
}
```

#### `GET /api/v1/parcels/search` & `GET /api/v1/parcels` — Search Property Parcels
* **Purpose & Use Case:** General lookup across commercial county tax assessor databases.
* **Query Parameters:**
  * `city` *(string, optional)*
  * `county` *(string, optional)*
  * `min_sqft` *(int, default: 10000)*
  * `source` *(string, optional)*: `nyc_pluto`, `king_county_gis`, `dallas_cad`, `tarrant_tad`.
  * `limit` *(int, default: 50)*

#### `GET /api/v1/parcels/dallas` & `GET /api/v1/parcels/tarrant` — Texas CAD Endpoints
* **Purpose & Use Case:** Quick-fetch pre-filtered commercial parcels specifically for Dallas County (DCAD) and Tarrant County (Fort Worth TAD).

#### `GET /api/v1/parcels/{parcel_id}` — Single Parcel Dossier
* **Purpose & Use Case:** Returns exact parcel boundaries, deed owner address, assessed market value, and linked permits.

---

### Module 4: Contractor Intelligence & Leaderboards

#### `GET /api/v1/contractors/leaderboard` — Contractor Win-Share & Volume
* **Purpose & Use Case:** Ranks commercial roofing contractors by permit volume, total pipeline valuation, and membrane preference (TPO vs EPDM vs Metal) within any jurisdiction. Powers the **Competitor Intelligence** view.
* **Query Parameters:**
  * `jurisdiction` *(string, optional)*: Filter rankings by city (e.g. `dallas_tx`).
  * `limit` *(int, default: 50)*
* **Response (200 OK):**
```json
{
  "total_contractors": 2092,
  "contractors": [
    {
      "contractor_id": "cont_8812",
      "contractor_name": "CENTIMARK CORPORATION",
      "total_permits": 142,
      "total_valuation": 34850000.0,
      "average_job_size": 245422.53,
      "market_share_percent": 6.8,
      "primary_roof_system": "TPO",
      "jurisdictions_active": ["dallas_tx", "fort_worth_tx", "seattle_sdci"],
      "last_permit_filed": "2024-09-18"
    }
  ]
}
```

---

### Module 5: Severe Weather & Storm Swath Intelligence

#### `GET /api/v1/storms/active-swaths` — Active NOAA Hail & Wind Swaths
* **Purpose & Use Case:** Returns GeoJSON / tabular storm polygons with maximum recorded hail diameter (e.g. 1.75" – 3.0" hail) and dates of impact.
* **Response (200 OK):**
```json
{
  "total_swaths": 20,
  "swaths": [
    {
      "storm_id": "storm_dfw_2024_03",
      "event_date": "2024-03-24",
      "max_hail_inches": 2.5,
      "max_wind_gust_mph": 75,
      "state": "TX",
      "cities_impacted": ["Dallas", "Irving", "Plano", "Fort Worth"],
      "estimated_commercial_parcels_exposed": 1420
    }
  ]
}
```

#### `GET /api/v1/storms/live-alerts` — Real-Time NOAA Warning Feed
* **Purpose & Use Case:** Live polling feed for active National Weather Service severe convective storm alerts.

---

### Module 6: Commercial Intelligence & Unresolved Exposure

#### `GET /api/v1/intelligence/unresolved-exposure` — Unresolved Hail Damage Dossier
* **Purpose & Use Case:** Cross-references parcels inside severe hail swaths against subsequent permit records. Returns commercial properties that **sustained severe hail damage (>1.5") but have never filed for a repair/reroof permit**. These are prime targets for storm restoration and insurance adjustments.
* **Query Parameters:**
  * `min_sqft` *(int, default: 25000)*: Minimum building footprint.
  * `min_hail_inches` *(float, default: 1.5)*: Minimum recorded hail size.
  * `storm_id` *(string, optional)*: Specific storm identifier.
  * `limit` *(int, default: 50)*
* **Response (200 OK):**
```json
{
  "total_unresolved_exposure": 184,
  "total_unclaimed_sqft": 8420000,
  "items": [
    {
      "parcel_id": "dfw_cad_008129",
      "address": "1200 METROPOLITAN PARKWAY, DALLAS, TX",
      "owner_name": "INDUSTRIAL LOGISTICS TRUST",
      "bldg_sqft": 142000,
      "storm_date": "2024-03-24",
      "hail_size_inches": 2.25,
      "months_since_storm": 7,
      "subsequent_permits_count": 0,
      "urgency_rating": "CRITICAL"
    }
  ]
}
```

---

### Module 7: Background Ingestion Jobs & Real-Time SSE Streaming

#### `POST /api/v1/jobs/trigger-sync` — Trigger Asynchronous Ingestion Job
* **Purpose & Use Case:** Initiates a background scraping or enrichment worker thread. Returns a `job_id` that can be streamed in real-time.
* **Headers:**
  * `X-Depoii-Key`: API key (required).
* **Request Body:**
```json
{
  "city_key": "dallas_tx"
}
```
* **Response (200 OK):**
```json
{
  "job_id": "job_e98f01a3",
  "status": "QUEUED",
  "city_key": "dallas_tx",
  "message": "Harvesting and normalization worker dispatched in background."
}
```

#### `GET /api/v1/jobs/{job_id}/stream` — Server-Sent Events (SSE) Live Feed
* **Purpose & Use Case:** Real-time push notification stream for Next.js UI progress bars during live municipal syncing.
* **Response:** `text/event-stream` returning events:
```text
event: progress
data: {"job_id": "job_e98f01a3", "progress_pct": 45, "permits_processed": 1200, "status": "RUNNING"}

event: completed
data: {"job_id": "job_e98f01a3", "progress_pct": 100, "status": "COMPLETED", "records_inserted": 2410}
```

---

### Module 8: Location Coverage & Geographic Hierarchy

#### `GET /api/v1/locations/hierarchy` — Full Geo Tree
* **Purpose & Use Case:** Returns active hierarchy of supported States -> Counties -> Municipalities -> Available Data Layers (Permits, Parcels, Storms).

#### `GET /api/v1/locations/states` & `GET /api/v1/locations/cities`
* **Purpose & Use Case:** Quick-select lists for state and city selector filters.

---

## 4. Error Handling & Status Codes

All errors return a standardized JSON structure:

```json
{
  "detail": "Descriptive reason for failure",
  "status_code": 404,
  "correlation_id": "req-9a8b7c6d"
}
```

* **`400 Bad Request`**: Malformed input parameters or invalid date strings.
* **`401 / 403 Forbidden`**: Missing or invalid `X-Depoii-Key` header on mutation endpoints.
* **`404 Not Found`**: Requested permit, parcel, or contractor ID does not exist.
* **`422 Unprocessable Entity`**: Pydantic schema validation failure (e.g. non-integer passed to `limit`).
* **`500 Internal Server Error`**: Database lock or unexpected exception (logged with stack trace and correlation ID).
