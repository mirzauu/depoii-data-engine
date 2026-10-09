"""
Daily Live NOAA Severe Storm Sync Daemon
-------------------------------------------
Continuously monitors NOAA / NWS Local Storm Reports (LSR) across all 11 core
metropolitan WFOs for real-time severe convective storms (Hail >= 1.0 in, Gust >= 60 mph).
Generates swath polygons, computes hail kinetics, and maintains an up-to-date storm catalog.

Usage:
    python daily_storm_daemon.py --now                # Run one-shot sync for past 48 hours
    python daily_storm_daemon.py --daemon --interval 86400   # Run recurring daily daemon
"""

import os
import sys
import time
import json
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
import httpx
from shapely.geometry import Point, MultiPoint

from harvest_noaa_storms import (
    WFO_CONFIGS,
    calculate_hail_physics,
    generate_swath_polygon,
    save_storms_to_db,
    IEM_LSR_URL,
    DB_PATH
)

STATE_FILE = os.path.join(os.path.dirname(__file__), "storm_daemon_state.json")


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "last_sync_utc": None,
        "total_storms_tracked": 0,
        "runs_completed": 0,
        "last_status": "INITIALIZED"
    }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def run_sync(lookback_days: int = 3):
    state = load_state()
    now_utc = datetime.now(timezone.utc)
    start_dt = now_utc - timedelta(days=lookback_days)
    
    sts = start_dt.strftime("%Y-%m-%dT00:00:00Z")
    ets = now_utc.strftime("%Y-%m-%dT23:59:59Z")
    print(f"\n[STORM DAEMON] Checking NOAA LSR from {sts} to {ets}...")

    total_new_storms = []
    with httpx.Client(timeout=45.0) as client:
        for wfo, cfg in WFO_CONFIGS.items():
            params = {
                "sts": sts,
                "ets": ets,
                "wfos": wfo,
                "types": "H,W"
            }
            try:
                r = client.get(IEM_LSR_URL, params=params)
                if r.status_code == 200:
                    feats = r.json().get("features", [])
                    # Group by date
                    daily_groups = {}
                    for f in feats:
                        props = f.get("properties", {})
                        geom = f.get("geometry", {})
                        coords = geom.get("coordinates")
                        if not coords or len(coords) < 2:
                            continue
                        mag = props.get("magf") or 0.0
                        ttype = props.get("typetext", "")
                        valid = props.get("valid", "")
                        if (ttype == "HAIL" and mag >= 1.00) or (ttype == "TSTM WND GST" and mag >= 60.0):
                            d_str = valid[:10]
                            if d_str not in daily_groups:
                                daily_groups[d_str] = {"coords": [], "hail": [], "wind": [], "counties": set()}
                            daily_groups[d_str]["coords"].append(coords)
                            if ttype == "HAIL":
                                daily_groups[d_str]["hail"].append(mag)
                            else:
                                daily_groups[d_str]["wind"].append(mag)
                            if props.get("county"):
                                daily_groups[d_str]["counties"].add(props["county"])

                    for d_str, g in daily_groups.items():
                        max_hail = max(g["hail"]) if g["hail"] else 0.0
                        max_wind = max(g["wind"]) if g["wind"] else 0.0
                        d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                        storm_name = f"{d_obj.strftime('%B %d, %Y')} {cfg['metro']} Severe Storm Event"
                        sid = f"STORM-{d_str}-{cfg['code']}"
                        poly = generate_swath_polygon(g["coords"])
                        physics = calculate_hail_physics(max_hail)

                        props_json = {
                            "fill_color": physics["fill_color"],
                            "stroke_color": physics["stroke_color"],
                            "mass_grams": physics["mass_grams"],
                            "terminal_velocity_mph": physics["terminal_velocity_mph"],
                            "kinetic_energy_joules": physics["kinetic_energy_joules"],
                            "severity_tier": physics["severity_tier"],
                            "radar_signature": cfg["radar"],
                            "total_reports": len(g["coords"]),
                            "max_wind_mph": max_wind,
                            "affected_counties": list(g["counties"]),
                            "polygon": poly
                        }
                        total_new_storms.append({
                            "id": sid,
                            "storm_name": storm_name,
                            "event_date": d_str,
                            "max_hail_inches": round(max_hail, 2),
                            "max_gust_mph": round(max_wind, 1),
                            "jurisdiction_id": cfg["jurisdiction_id"],
                            "properties": json.dumps(props_json)
                        })
            except Exception as e:
                print(f"  [ERROR] {wfo}: {e}")

    inserted, updated = save_storms_to_db(total_new_storms)
    print(f"[STORM DAEMON] Sync completed. Inserted: {inserted}, Updated: {updated}.")

    state["last_sync_utc"] = now_utc.isoformat()
    state["runs_completed"] += 1
    state["last_status"] = "HEALTHY"
    save_state(state)


def main():
    parser = argparse.ArgumentParser(description="NOAA Daily Severe Storm Sync Daemon")
    parser.add_argument("--now", action="store_true", help="Run single sync pass immediately")
    parser.add_argument("--daemon", action="store_true", help="Run continuously in background")
    parser.add_argument("--interval", type=int, default=86400, help="Interval in seconds between syncs (default 86400 = 24h)")
    parser.add_argument("--lookback", type=int, default=3, help="Lookback days to check (default 3)")
    args = parser.parse_args()

    if args.daemon:
        print(f"[DAEMON] Starting Daily NOAA Storm Sync Daemon (Interval: {args.interval}s, Lookback: {args.lookback} days)...")
        while True:
            try:
                run_sync(lookback_days=args.lookback)
            except Exception as e:
                print(f"[DAEMON ERROR] {e}")
            time.sleep(args.interval)
    else:
        run_sync(lookback_days=args.lookback)


if __name__ == "__main__":
    main()
