# Depoii Data Engine v2.0

> Autonomous Data Science, Normalization & Extraction Engine for Depoii Commercial Roofing Intelligence.

## Overview
The **Depoii Data Engine** is a high-throughput, standalone FastAPI backend microservice that:
1. Ingests municipal building permits across Tier 1 (Socrata Open Data) and Tier 2 (Accela Citizen Access via per-city configuration registry).
2. Cleans, normalizes, and deduplicates records across disparate government data models into the canonical `DepoiiNormalizedPermit` schema.
3. Computes spatial cross-references directly in PostGIS (hail storm polygons vs. commercial parcels).
4. Estimates commercial roof replacement costs and unresolved loss exposure.
5. Exposes a typed, secured REST + SSE stream API to the Depoii Next.js dashboard.

---

## Quickstart (Local Development)

### 1. Requirements
- Python 3.11+
- Virtual environment (`.venv`)

### 2. Setup
```bash
# Enter directory
cd depoii-data-engine

# Activate virtual environment
.\.venv\Scripts\activate   # Windows
# or: source .venv/bin/activate (Linux/macOS)

# Run tests
pytest -v

# Start development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

---

## Docker Deployment (Production)

To launch the full stack (PostgreSQL 16 + PostGIS 3.4, Redis 7, Celery Workers, Celery Beat, FastAPI Engine):

```bash
docker compose up -d
```

---

## Project Structure
- `app/api/v1/`: API endpoints (`health`, `permits`, `contractors`, `storms`, `intelligence`)
- `app/core/`: Database engine, security (`X-Depoii-Key`), structured logging with correlation IDs
- `app/schemas/`: Pydantic v2 schemas matching Depoii canonical contracts
- `app/models/`: SQLAlchemy 2.0 ORM PostGIS entities
- `app/extraction/`: Async Socrata client and Playwright scrapers
- `app/science/`: PostGIS spatial queries, RapidFuzz deduplication, NLP membrane extractor, heuristic cost estimator
- `city_configs/`: Per-jurisdiction scraper configuration YAML files (`dallas_tx.yaml`, `fort_worth_tx.yaml`, etc.)
- `shared/schemas/`: Shared JSON schema contracts for TypeScript/Python interoperability
