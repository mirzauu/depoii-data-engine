import httpx
from typing import List, Dict, Any, Optional
from app.core.logging import logger

TARRANT_ARCGIS_QUERY_URL = "https://mapit.tarrantcounty.com/arcgis/rest/services/Dynamic/TADParcels/MapServer/0/query"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Depoii-Data-Engine/1.0",
    "Accept": "application/json",
}


class TarrantParcelClient:
    """
    Direct extractor for Tarrant County (Fort Worth & surrounding DFW municipalities)
    property parcels via public ESRI ArcGIS REST MapServer.
    Provides $0-cost parcel boundaries, square footage, valuations, and owner data.
    """

    def __init__(self, base_url: str = TARRANT_ARCGIS_QUERY_URL):
        self.base_url = base_url

    def _compute_centroid(self, rings: List[List[List[float]]]) -> Optional[Dict[str, float]]:
        """
        Computes the center coordinate (latitude, longitude) from ArcGIS polygon rings.
        Rings are in [longitude, latitude] (WGS 84 / 4326).
        """
        all_points = [pt for ring in rings for pt in ring]
        if not all_points:
            return None
        avg_lon = sum(p[0] for p in all_points) / len(all_points)
        avg_lat = sum(p[1] for p in all_points) / len(all_points)
        return {"latitude": round(avg_lat, 6), "longitude": round(avg_lon, 6)}

    def _normalize_feature(self, feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Normalizes a raw Tarrant County ESRI feature into Depoii's canonical parcel dictionary.
        """
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry", {})
        rings = geom.get("rings", [])

        centroid = self._compute_centroid(rings)
        if not centroid:
            return None

        account = str(attrs.get("ACCOUNT") or attrs.get("OBJECTID") or "").strip()
        address = str(attrs.get("SITUS_ADDR") or "").strip().title()
        city = str(attrs.get("CITY") or "Fort Worth").strip().title()
        owner = str(attrs.get("OWNER_NAME") or "Unknown Owner").strip().title()
        zip_code = str(attrs.get("ZIPCODE") or "").strip()

        living_sqft = float(attrs.get("LIVING_ARE") or 0.0)
        land_sqft = float(attrs.get("LAND_SQFT") or 0.0)
        year_built = int(attrs.get("YEAR_BUILT")) if attrs.get("YEAR_BUILT") and attrs.get("YEAR_BUILT") > 1800 else None
        total_val = float(attrs.get("TOTAL_VALU") or 0.0)
        impr_val = float(attrs.get("IMPR_VALUE") or 0.0)

        sqft = int(living_sqft) if living_sqft > 0 else int(land_sqft)

        # Property type classification heuristic
        desc = str(attrs.get("DESCR") or "").strip()
        if living_sqft > 100000 or land_sqft > 200000:
            property_type = "Mega Industrial Logistics / Distribution Facility"
        elif living_sqft > 40000 or land_sqft > 50000:
            property_type = "Commercial Warehouse & Flex Business Park"
        elif "COMM" in desc.upper() or total_val > 1000000:
            property_type = "Commercial Real Estate Asset"
        else:
            property_type = "Commercial Facility"

        return {
            "id": f"TAD-PARCEL-{account}",
            "account_number": account,
            "address": address,
            "city": city,
            "county": "Tarrant County",
            "state": "TX",
            "zip_code": zip_code,
            "building_sqft": sqft,
            "land_sqft": int(land_sqft),
            "year_built": year_built,
            "property_type": property_type,
            "owner_name": owner,
            "total_valuation": total_val,
            "improvement_valuation": impr_val,
            "data_source": "Tarrant Appraisal District (TAD)",
            "latitude": centroid["latitude"],
            "longitude": centroid["longitude"],
        }

    async def fetch_commercial_parcels(
        self,
        min_sqft: int = 20000,
        city_filter: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Queries Tarrant County MapServer for commercial parcels meeting valuation and square footage thresholds.
        Supports pagination to harvest up to requested limit.
        """
        where_clauses = ["IMPR_VALUE >= 1000000 AND (BEDROOMS = 0 OR BEDROOMS IS NULL)"]
        if min_sqft > 0:
            where_clauses.append(f"(LAND_SQFT >= {min_sqft} OR LIVING_ARE >= {min_sqft})")
        if city_filter:
            where_clauses.append(f"UPPER(CITY) LIKE '%{city_filter.upper()}%'")

        where_query = " AND ".join(where_clauses)
        results = []
        offset = 0
        page_size = 100

        logger.info(f"[TarrantParcelClient] Querying TAD: where='{where_query}', target_limit={limit}")

        async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
            while len(results) < limit:
                batch_limit = min(page_size, limit - len(results))
                params = {
                    "where": where_query,
                    "outFields": "OBJECTID,ACCOUNT,TAXPIN,OWNER_NAME,SITUS_ADDR,CITY,ZIPCODE,YEAR_BUILT,LIVING_ARE,LAND_SQFT,TOTAL_VALU,DESCR",
                    "resultRecordCount": str(batch_limit),
                    "resultOffset": str(offset),
                    "f": "json",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "orderByFields": "LIVING_ARE DESC",
                }

                resp = await client.get(self.base_url, params=params, headers=DEFAULT_HEADERS)
                resp.raise_for_status()
                data = resp.json()

                if "error" in data:
                    logger.error(f"[TarrantParcelClient] Error from ArcGIS: {data['error']}")
                    break

                features = data.get("features", [])
                if not features:
                    break

                for feat in features:
                    norm = self._normalize_feature(feat)
                    if norm and norm["building_sqft"] >= min_sqft:
                        results.append(norm)

                offset += len(features)
                if len(features) < batch_limit:
                    break

            logger.info(f"[TarrantParcelClient] Successfully normalized {len(results)} Tarrant parcels.")
            return results
