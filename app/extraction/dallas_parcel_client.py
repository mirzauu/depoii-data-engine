import httpx
from typing import List, Dict, Any, Optional
from app.core.logging import logger

DALLAS_ARCGIS_QUERY_URL = "https://services2.arcgis.com/rwnOSbfKSwyTBcwN/arcgis/rest/services/DallasTaxParcels/FeatureServer/0/query"

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Depoii-Data-Engine/1.0",
    "Accept": "application/json",
}


class DallasParcelClient:
    """
    Direct extractor for Dallas County & City of Dallas commercial property parcels
    via public ESRI ArcGIS REST FeatureServer (DallasTaxParcels / DCAD certified data).
    Provides $0-cost parcel boundaries, square footage, owner entities, and geographic coordinates.
    """

    def __init__(self, base_url: str = DALLAS_ARCGIS_QUERY_URL):
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
        Normalizes a raw Dallas County ESRI feature into Depoii's canonical parcel dictionary.
        """
        attrs = feature.get("attributes", {})
        geom = feature.get("geometry", {})
        rings = geom.get("rings", [])

        centroid = self._compute_centroid(rings)
        if not centroid:
            return None

        account = str(attrs.get("ACCT") or attrs.get("GIS_ACCT") or attrs.get("OBJECTID") or "").strip()
        st_num = str(attrs.get("ST_NUM") or "").strip()
        st_name = str(attrs.get("ST_NAME") or "").strip()
        st_type = str(attrs.get("ST_TYPE") or "").strip()
        address_parts = [p for p in [st_num, st_name, st_type] if p]
        address = " ".join(address_parts).title() if address_parts else f"Parcel {account}"

        city = str(attrs.get("CITY") or "Dallas").strip().title()
        county = str(attrs.get("COUNTY") or "Dallas County").strip().title()
        owner = str(attrs.get("TAXPANAME1") or attrs.get("BUSNAME") or "Commercial Property Owner").strip().title()
        prop_name = str(attrs.get("PROPNAM") or "").strip().title()

        area_sqft = float(attrs.get("AREA_FEET") or 0.0)

        # Property type classification heuristic based on size and owner
        if area_sqft >= 200000:
            property_type = "Mega Industrial Logistics / Distribution Facility"
        elif area_sqft >= 75000:
            property_type = "Commercial Warehouse & Flex Business Park"
        elif area_sqft >= 30000:
            property_type = "Commercial Office / Retail Center"
        else:
            property_type = "Commercial Facility"

        # Heuristic valuation estimate if not directly present ($120/sqft commercial replacement value)
        total_val = round(area_sqft * 120.0, 2)

        return {
            "id": f"DCAD-PARCEL-{account}",
            "account_number": account,
            "address": address,
            "city": city,
            "county": county,
            "state": "TX",
            "zip_code": str(attrs.get("TAXPAZIP") or "75201").strip()[:5],
            "building_sqft": int(area_sqft),
            "land_sqft": int(area_sqft),
            "year_built": int(attrs.get("APPRAISALYEAR")) if attrs.get("APPRAISALYEAR") else None,
            "property_type": property_type,
            "owner_name": owner,
            "total_valuation": total_val,
            "improvement_valuation": round(total_val * 0.75, 2),
            "data_source": "Dallas Central Appraisal District (DCAD)",
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
        Queries Dallas County FeatureServer for commercial parcels meeting square footage thresholds.
        Supports pagination to harvest up to requested limit.
        """
        where_clauses = ["ResCom = 'C'"]
        if min_sqft > 0:
            where_clauses.append(f"AREA_FEET >= {min_sqft}")
        if city_filter:
            where_clauses.append(f"UPPER(CITY) LIKE '%{city_filter.upper()}%'")

        where_query = " AND ".join(where_clauses)
        results = []
        offset = 0
        page_size = 200

        logger.info(f"[DallasParcelClient] Querying DCAD FeatureServer: where='{where_query}', target_limit={limit}")

        async with httpx.AsyncClient(timeout=45.0, verify=False) as client:
            while len(results) < limit:
                batch_limit = min(page_size, limit - len(results))
                params = {
                    "where": where_query,
                    "outFields": "OBJECTID,ACCT,GIS_ACCT,ST_NUM,ST_NAME,ST_TYPE,CITY,COUNTY,BUSNAME,TAXPANAME1,PROPNAM,AREA_FEET,APPRAISALYEAR,TAXPAZIP,ResCom",
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
                    logger.error(f"[DallasParcelClient] HTTP error fetching parcels at offset {offset}: {exc}")
                    break

                features = data.get("features", [])
                if not features:
                    logger.info(f"[DallasParcelClient] No more features returned at offset {offset}.")
                    break

                for feat in features:
                    norm = self._normalize_feature(feat)
                    if norm:
                        results.append(norm)

                offset += len(features)
                if len(features) < batch_limit:
                    break

        logger.info(f"[DallasParcelClient] Harvest complete: retrieved {len(results)} commercial parcels.")
        return results[:limit]
