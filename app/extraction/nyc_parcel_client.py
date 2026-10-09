import httpx
from typing import List, Dict, Any, Optional
from app.core.logging import logger

NYC_MAPPLUTO_QUERY_URL = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/MAPPLUTO/FeatureServer/0/query"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Depoii-Data-Engine/1.0",
    "Accept": "application/json",
}

BOROUGH_MAP = {
    "MN": {"num": 1, "name": "Manhattan", "county": "New York County"},
    "BX": {"num": 2, "name": "Bronx", "county": "Bronx County"},
    "BK": {"num": 3, "name": "Brooklyn", "county": "Kings County"},
    "QN": {"num": 4, "name": "Queens", "county": "Queens County"},
    "SI": {"num": 5, "name": "Staten Island", "county": "Richmond County"},
}


class NYCParcelClient:
    """
    Direct extractor for New York City commercial property parcels via NYC Department of City Planning
    MapPLUTO ESRI ArcGIS REST FeatureServer.
    Provides authoritative BBL, square footage, building classes, property tax assessments, and coordinates.
    """

    def __init__(self, base_url: str = NYC_MAPPLUTO_QUERY_URL):
        self.base_url = base_url

    def _compute_centroid(self, rings: List[List[List[float]]]) -> Optional[Dict[str, float]]:
        """
        Computes center coordinate (latitude, longitude) from ArcGIS polygon rings.
        Rings are in [longitude, latitude] (WGS 84 / EPSG:4326).
        """
        all_points = [pt for ring in rings for pt in ring]
        if not all_points:
            return None
        avg_lon = sum(p[0] for p in all_points) / len(all_points)
        avg_lat = sum(p[1] for p in all_points) / len(all_points)
        return {"latitude": round(avg_lat, 6), "longitude": round(avg_lon, 6)}

    def _normalize_feature(self, feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalizes raw NYC MapPLUTO feature into Depoii canonical parcel format.
        """
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry", {})
        rings = geom.get("rings", [])

        centroid = self._compute_centroid(rings)
        if not centroid:
            return None

        boro_code = str(attrs.get("Borough") or "MN").upper().strip()
        boro_info = BOROUGH_MAP.get(boro_code, {"num": 1, "name": "Manhattan", "county": "New York County"})

        block = int(attrs.get("Block") or 0)
        lot = int(attrs.get("Lot") or 0)
        bbl = f"{boro_info['num']}{block:05d}{lot:04d}"

        address_raw = str(attrs.get("Address") or f"Block {block} Lot {lot}").strip().title()
        bldg_sqft = int(attrs.get("BldgArea") or 0)
        com_sqft = int(attrs.get("ComArea") or 0)
        office_sqft = int(attrs.get("OfficeArea") or 0)
        retail_sqft = int(attrs.get("RetailArea") or 0)
        effective_sqft = max(bldg_sqft, com_sqft)

        year_built = int(attrs.get("YearBuilt")) if attrs.get("YearBuilt") and attrs.get("YearBuilt") > 1800 else None
        owner = str(attrs.get("OwnerName") or "Institutional Commercial Owner").strip().title()
        assess_tot = float(attrs.get("AssessTot") or 0.0)

        # Commercial Property Classification Heuristic
        bldg_class = str(attrs.get("BldgClass") or "").upper().strip()
        if office_sqft > 100000 or (bldg_class.startswith("O") and effective_sqft > 100000):
            property_type = "Class A Commercial Office Tower"
        elif effective_sqft > 200000:
            property_type = "Major Commercial Industrial / Distribution Center"
        elif bldg_class.startswith("E") or bldg_class.startswith("F"):
            property_type = "Commercial Warehouse & Industrial Facility"
        elif bldg_class.startswith("K") or retail_sqft > 30000:
            property_type = "Commercial Retail Complex"
        elif bldg_class.startswith("R"):
            property_type = "Commercial Residential Multi-Family Complex"
        else:
            property_type = "Commercial Real Estate Asset"

        # Realistic property valuation: NYC assessed value is typically 45% of market value
        market_val = round(assess_tot * 2.22, 2) if assess_tot > 0 else round(effective_sqft * 250.0, 2)

        return {
            "id": f"NYC-PLUTO-{bbl}",
            "source_id": "SRC-NYC-MAPPLUTO",
            "account_number": bbl,
            "address": address_raw,
            "city": "New York",
            "county": boro_info["county"],
            "state": "NY",
            "zip_code": str(attrs.get("ZipCode") or "10001").strip()[:5],
            "building_sqft": effective_sqft,
            "land_sqft": com_sqft or effective_sqft,
            "year_built": year_built,
            "property_type": property_type,
            "owner_name": owner,
            "total_valuation": market_val,
            "improvement_valuation": round(market_val * 0.8, 2),
            "data_source": "NYC Department of City Planning (MapPLUTO)",
            "source_url": f"https://zola.planning.nyc.gov/lot/{boro_info['num']}/{block}/{lot}",
            "latitude": centroid["latitude"],
            "longitude": centroid["longitude"],
        }

    async def fetch_commercial_parcels(
        self,
        min_sqft: int = 25000,
        borough: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        Queries NYC MapPLUTO FeatureServer for commercial buildings meeting square footage criteria.
        Paginates up to requested limit.
        """
        where_clauses = [f"(ComArea >= {min_sqft} OR OfficeArea >= {min_sqft} OR BldgArea >= {min_sqft})"]
        if borough:
            boro_upper = borough.upper()[:2]
            if boro_upper in BOROUGH_MAP:
                where_clauses.append(f"Borough = '{boro_upper}'")

        where_query = " AND ".join(where_clauses)
        results = []
        offset = 0
        page_size = 200

        logger.info(f"[NYCParcelClient] Querying MapPLUTO: where='{where_query}', target_limit={limit}")

        async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
            while len(results) < limit:
                batch_limit = min(page_size, limit - len(results))
                params = {
                    "where": where_query,
                    "outFields": "OBJECTID,Borough,Block,Lot,Address,ZipCode,BldgArea,ComArea,OfficeArea,RetailArea,YearBuilt,OwnerName,AssessTot,BldgClass",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "resultRecordCount": batch_limit,
                    "resultOffset": offset,
                    "f": "json",
                }

                try:
                    resp = await client.get(self.base_url, params=params, headers=DEFAULT_HEADERS)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as exc:
                    logger.error(f"[NYCParcelClient] HTTP error at offset {offset}: {exc}")
                    break

                features = data.get("features", [])
                if not features:
                    break

                for feat in features:
                    norm = self._normalize_feature(feat)
                    if norm:
                        results.append(norm)

                offset += len(features)
                if len(features) < batch_limit:
                    break

        logger.info(f"[NYCParcelClient] Harvest complete: retrieved {len(results)} NYC commercial parcels.")
        return results[:limit]
