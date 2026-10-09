import time
from datetime import datetime, timezone, time as dt_time
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
import httpx

from app.schemas.hail_events_schema import (
    CenterCoord,
    HailEventSummary,
    HailReportItem,
    WarningItem,
    SelectedEventDetail,
    HailEventsCatalogResponse
)
from app.core.logging import logger

CENTRAL_TZ = ZoneInfo("America/Chicago")
UTC_TZ = ZoneInfo("UTC")

IEM_LSR_URL = "https://mesonet.agron.iastate.edu/geojson/lsr.geojson"
IEM_SBW_URL = "https://mesonet.agron.iastate.edu/geojson/sbw.geojson"

# In-memory cache with 10-minute TTL
_LSR_CACHE: Dict[str, Dict[str, Any]] = {}
_WARNINGS_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600

STATE_REGIONS = {
    "TX": "North Texas",
    "NY": "New York Metro",
    "FL": "Florida",
    "IL": "Chicago Metro",
    "OH": "Ohio Valley",
    "WA": "Puget Sound",
    "MA": "Massachusetts",
    "LA": "Louisiana",
    "MD": "Mid-Atlantic"
}


def _get_region_name(state: str) -> str:
    return STATE_REGIONS.get(state.upper(), state.upper())


def _format_event_names(day_str: str, state: str) -> tuple[str, str]:
    try:
        dt = datetime.strptime(day_str, "%Y-%m-%d")
        long_date = dt.strftime("%B %d, %Y").replace(" 0", " ")
        short_date = dt.strftime("%b %d, %Y").replace(" 0", " ")
    except Exception:
        long_date = day_str
        short_date = day_str

    region = _get_region_name(state)
    name = f"{long_date} — {region} hail reports"
    short_name = f"{short_date} · {region}"
    return name, short_name


async def fetch_lsr_reports(state: str, since: str) -> List[Dict[str, Any]]:
    cache_key = f"{state.upper()}_{since}"
    now = time.time()

    if cache_key in _LSR_CACHE:
        entry = _LSR_CACHE[cache_key]
        if now - entry["timestamp"] < CACHE_TTL_SECONDS:
            return entry["features"]

    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = f"{IEM_LSR_URL}?states={state.upper()}&sts={since}T00:00:00Z&ets={now_utc_str}"
    logger.info(f"[HAIL EVENTS] Fetching NOAA LSR from IEM: {url}")

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                features = res.json().get("features", [])
                _LSR_CACHE[cache_key] = {"timestamp": now, "features": features}
                return features
            else:
                logger.warning(f"[HAIL EVENTS] IEM LSR returned status {res.status_code}")
    except Exception as exc:
        logger.error(f"[HAIL EVENTS] Error fetching IEM LSR: {exc}")

    # Fallback to stale cache if available
    if cache_key in _LSR_CACHE:
        return _LSR_CACHE[cache_key]["features"]
    return []


async def fetch_warnings_for_day(state: str, day_str: str) -> tuple[List[WarningItem], float]:
    cache_key = f"{state.upper()}_{day_str}"
    now = time.time()

    if cache_key in _WARNINGS_CACHE:
        entry = _WARNINGS_CACHE[cache_key]
        if now - entry["timestamp"] < CACHE_TTL_SECONDS:
            return entry["warnings"], entry["max_warning_hail"]

    # Calculate UTC window corresponding to the full Central Time day
    try:
        d = datetime.strptime(day_str, "%Y-%m-%d")
        start_utc = datetime.combine(d.date(), dt_time.min, CENTRAL_TZ).astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_utc = datetime.combine(d.date(), dt_time.max, CENTRAL_TZ).astimezone(UTC_TZ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        start_utc = f"{day_str}T00:00:00Z"
        end_utc = f"{day_str}T23:59:59Z"

    url = f"{IEM_SBW_URL}?states={state.upper()}&sts={start_utc}&ets={end_utc}&phenomena=SV"
    logger.info(f"[HAIL EVENTS] Fetching NWS SBW warnings: {url}")

    warnings: List[WarningItem] = []
    max_warning_hail = 0.0

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.get(url)
            if res.status_code == 200:
                features = res.json().get("features", [])
                
                # Deduplicate by (wfo, eventid) keeping the most severe update
                unique_events: Dict[tuple, Dict[str, Any]] = {}
                for f in features:
                    p = f.get("properties", {})
                    wfo = p.get("wfo", "")
                    ev_id = p.get("eventid", 0)
                    key = (wfo, ev_id)
                    hail_tag = float(p.get("max_hailtag") or p.get("hailtag") or 0.0)
                    if key not in unique_events or hail_tag > unique_events[key]["hail_tag"]:
                        unique_events[key] = {"feature": f, "hail_tag": hail_tag}

                for item in unique_events.values():
                    f = item["feature"]
                    p = f.get("properties", {})
                    geom = f.get("geometry", {})
                    hail_tag = item["hail_tag"]
                    wind_tag = int(p.get("max_windtag") or p.get("windtag") or 0)

                    issue_raw = p.get("issue") or p.get("polygon_begin") or ""
                    expire_raw = p.get("expire") or p.get("polygon_end") or ""

                    try:
                        iss_dt = datetime.fromisoformat(issue_raw.replace("Z", "+00:00")).astimezone(CENTRAL_TZ)
                        issued_iso = iss_dt.isoformat()
                    except Exception:
                        issued_iso = issue_raw

                    try:
                        exp_dt = datetime.fromisoformat(expire_raw.replace("Z", "+00:00")).astimezone(CENTRAL_TZ)
                        expire_iso = exp_dt.isoformat()
                    except Exception:
                        expire_iso = expire_raw

                    tier = "core" if hail_tag >= 2.0 else "envelope"
                    basis = "Warning hail tag is 2 inches or larger" if tier == "core" else "Warning hail tag is under 2 inches"

                    if hail_tag > max_warning_hail:
                        max_warning_hail = hail_tag

                    warnings.append(WarningItem(
                        event_id=int(p.get("eventid") or 0),
                        hail_tag_inches=round(hail_tag, 2),
                        wind_tag_mph=wind_tag,
                        issued=issued_iso,
                        expires=expire_iso,
                        tier=tier,
                        basis=basis,
                        geometry=geom or {"type": "Polygon", "coordinates": []}
                    ))

                # Sort warnings by hail tag desc, issued desc
                warnings.sort(key=lambda w: (w.hail_tag_inches, w.issued), reverse=True)
                _WARNINGS_CACHE[cache_key] = {"timestamp": now, "warnings": warnings, "max_warning_hail": max_warning_hail}
                return warnings, max_warning_hail
    except Exception as exc:
        logger.error(f"[HAIL EVENTS] Error fetching warnings: {exc}")

    if cache_key in _WARNINGS_CACHE:
        return _WARNINGS_CACHE[cache_key]["warnings"], _WARNINGS_CACHE[cache_key]["max_warning_hail"]

    return [], 0.0


async def get_hail_events_catalog(
    state: str = "TX",
    since: str = "2024-03-01",
    min_hail_inches: float = 1.5,
    event_date: Optional[str] = None
) -> HailEventsCatalogResponse:
    """
    Builds the complete hail-report catalog grouping NWS reports by US Central calendar day.
    Filters days with max_hail >= min_hail_inches and report_count >= 2.
    Returns newest 12 days and detailed reports/warning polygons for selected event_date.
    """
    raw_features = await fetch_lsr_reports(state=state, since=since)

    # Group valid hail reports by calendar day in US Central time
    daily_reports_map: Dict[str, List[HailReportItem]] = {}

    for idx, feat in enumerate(raw_features):
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue

        # Filter strictly for genuine hail reports in the requested state
        st = (props.get("state") or props.get("st") or "").upper()
        if st and st != state.upper():
            continue

        ttype = (props.get("typetext") or "").upper()
        if ttype != "HAIL" and props.get("type") != "H":
            continue

        valid_raw = props.get("valid", "")
        if not valid_raw:
            continue

        try:
            dt_utc = datetime.fromisoformat(valid_raw.replace("Z", "+00:00"))
            dt_central = dt_utc.astimezone(CENTRAL_TZ)
            day_str = dt_central.strftime("%Y-%m-%d")
            valid_iso = dt_central.isoformat()
        except Exception:
            continue

        mag = float(props.get("magf") or 0.0)
        rep_id = f"lsr-{props.get('product_id') or feat.get('id') or idx}"
        
        # Qualifier stays NWS code: M measured, E estimated, or empty string
        qual_raw = (props.get("qualifier") or "").upper().strip()
        qualifier = qual_raw if qual_raw in ("M", "E") else ""

        report_item = HailReportItem(
            id=rep_id,
            valid=valid_iso,
            latitude=round(float(coords[1]), 4),
            longitude=round(float(coords[0]), 4),
            hail_inches=round(mag, 2),
            qualifier=qualifier,
            city=(props.get("city") or "").upper(),
            county=(props.get("county") or "").upper(),
            source=props.get("source") or "NWS",
            remark=props.get("remark") or ""
        )

        if day_str not in daily_reports_map:
            daily_reports_map[day_str] = []
        daily_reports_map[day_str].append(report_item)

    # Filter and compile event days
    all_passing_events: List[HailEventSummary] = []

    for day_str, reps in sorted(daily_reports_map.items(), reverse=True):
        max_hail = max(r.hail_inches for r in reps)
        report_count = len(reps)

        # Rule: largest report >= min_hail_inches AND at least 2 reports
        if max_hail >= min_hail_inches and report_count >= 2:
            name, short_name = _format_event_names(day_str, state)
            avg_lat = round(sum(r.latitude for r in reps) / report_count, 2)
            avg_lon = round(sum(r.longitude for r in reps) / report_count, 2)

            all_passing_events.append(HailEventSummary(
                id=day_str,
                event_date=day_str,
                name=name,
                short_name=short_name,
                max_hail_inches=round(max_hail, 2),
                report_count=report_count,
                max_warning_hail_inches=0.0,
                center=CenterCoord(latitude=avg_lat, longitude=avg_lon)
            ))

    # Keep newest 12 days
    newest_12_events = all_passing_events[:12]

    # Determine selected event day
    target_date = event_date if event_date else (newest_12_events[0].event_date if newest_12_events else None)

    selected_detail: Optional[SelectedEventDetail] = None

    if target_date:
        # Check if target_date exists in passing events
        matching_event = next((e for e in all_passing_events if e.event_date == target_date), None)
        if not matching_event and target_date in daily_reports_map:
            reps = daily_reports_map[target_date]
            max_hail = max(r.hail_inches for r in reps)
            name, short_name = _format_event_names(target_date, state)
            avg_lat = round(sum(r.latitude for r in reps) / len(reps), 2)
            avg_lon = round(sum(r.longitude for r in reps) / len(reps), 2)
            matching_event = HailEventSummary(
                id=target_date,
                event_date=target_date,
                name=name,
                short_name=short_name,
                max_hail_inches=round(max_hail, 2),
                report_count=len(reps),
                max_warning_hail_inches=0.0,
                center=CenterCoord(latitude=avg_lat, longitude=avg_lon)
            )

        if matching_event:
            # Fetch warning polygons for target day
            warnings, max_warn_hail = await fetch_warnings_for_day(state=state, day_str=target_date)
            matching_event.max_warning_hail_inches = round(max_warn_hail, 2)

            # Also update in newest_12_events if present
            for ev in newest_12_events:
                if ev.event_date == target_date:
                    ev.max_warning_hail_inches = round(max_warn_hail, 2)

            reports_for_day = daily_reports_map.get(target_date, [])
            # Sort reports by hail_inches desc, valid desc
            reports_for_day.sort(key=lambda r: (r.hail_inches, r.valid), reverse=True)

            selected_detail = SelectedEventDetail(
                id=matching_event.id,
                event_date=matching_event.event_date,
                name=matching_event.name,
                short_name=matching_event.short_name,
                max_hail_inches=matching_event.max_hail_inches,
                report_count=matching_event.report_count,
                max_warning_hail_inches=matching_event.max_warning_hail_inches,
                center=matching_event.center,
                reports=reports_for_day,
                warnings=warnings
            )

    return HailEventsCatalogResponse(
        source="NWS local storm reports and storm-based warnings, via Iowa Environmental Mesonet",
        events=newest_12_events,
        selected=selected_detail
    )
