import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import httpx
from app.config import settings
from app.core.logging import logger


@dataclass
class SocrataFetchResult:
    domain: str
    dataset_id: str
    is_modified: bool
    status_code: int
    etag: Optional[str]
    records: List[Dict[str, Any]]
    total_records: int
    error: Optional[str] = None


class SocrataClient:
    """
    High-performance async client for Socrata Open Data APIs (SODA).
    Implements:
    - ETag / If-None-Match conditional requests to prevent redundant ingestion (Fix #1)
    - Automatic pagination via $limit and $offset
    - App token authentication
    - Rate limit throttling
    """
    def __init__(
        self,
        app_token: Optional[str] = None,
        timeout: float = 30.0,
        requests_per_minute: int = 60,
    ):
        self.app_token = app_token or settings.SOCRATA_APP_TOKEN
        self.timeout = timeout
        self.delay_between_requests = 60.0 / requests_per_minute

    def _build_headers(self, etag: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "DepoiiDataEngine/2.0 (+https://depoii.com)",
        }
        if self.app_token:
            headers["X-App-Token"] = self.app_token
        if etag:
            headers["If-None-Match"] = etag
        return headers

    async def fetch_page(
        self,
        client: httpx.AsyncClient,
        domain: str,
        dataset_id: str,
        limit: int = 1000,
        offset: int = 0,
        etag: Optional[str] = None,
        where_clause: Optional[str] = None,
        order_by: Optional[str] = None,
    ) -> SocrataFetchResult:
        """
        Fetches a single page of records from a Socrata SODA endpoint.
        """
        url = f"https://{domain}/resource/{dataset_id}.json"
        params: Dict[str, Any] = {
            "$limit": limit,
            "$offset": offset,
        }
        if where_clause:
            params["$where"] = where_clause
        if order_by:
            params["$order"] = order_by

        headers = self._build_headers(etag=etag if offset == 0 else None)

        try:
            response = await client.get(url, params=params, headers=headers, timeout=self.timeout)

            # 304 Not Modified: data hasn't changed since last sync
            if response.status_code == 304:
                logger.info(f"[Socrata] 304 Not Modified for {domain}/{dataset_id}")
                return SocrataFetchResult(
                    domain=domain,
                    dataset_id=dataset_id,
                    is_modified=False,
                    status_code=304,
                    etag=etag,
                    records=[],
                    total_records=0,
                )

            if response.status_code != 200:
                error_msg = f"Socrata error HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"[Socrata] {error_msg}")
                return SocrataFetchResult(
                    domain=domain,
                    dataset_id=dataset_id,
                    is_modified=True,
                    status_code=response.status_code,
                    etag=None,
                    records=[],
                    total_records=0,
                    error=error_msg,
                )

            new_etag = response.headers.get("ETag")
            records = response.json()
            if not isinstance(records, list):
                records = []

            return SocrataFetchResult(
                domain=domain,
                dataset_id=dataset_id,
                is_modified=True,
                status_code=200,
                etag=new_etag,
                records=records,
                total_records=len(records),
            )

        except Exception as e:
            logger.error(f"[Socrata] Connection error querying {url}: {e}")
            return SocrataFetchResult(
                domain=domain,
                dataset_id=dataset_id,
                is_modified=True,
                status_code=500,
                etag=None,
                records=[],
                total_records=0,
                error=str(e),
            )

    async def fetch_all_pages(
        self,
        domain: str,
        dataset_id: str,
        etag: Optional[str] = None,
        page_size: int = 1000,
        max_records: int = 10000,
        where_clause: Optional[str] = None,
        order_by: Optional[str] = None,
    ) -> SocrataFetchResult:
        """
        Paginates through all records until exhausted or max_records reached.
        """
        all_records: List[Dict[str, Any]] = []
        offset = 0
        final_etag = etag

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while offset < max_records:
                page_result = await self.fetch_page(
                    client=client,
                    domain=domain,
                    dataset_id=dataset_id,
                    limit=page_size,
                    offset=offset,
                    etag=final_etag if offset == 0 else None,
                    where_clause=where_clause,
                    order_by=order_by,
                )

                # If first request was 304, exit early
                if offset == 0 and not page_result.is_modified:
                    return page_result

                if page_result.status_code != 200 or not page_result.records:
                    if offset == 0 and page_result.error:
                        return page_result
                    break

                if offset == 0:
                    final_etag = page_result.etag

                all_records.extend(page_result.records)

                if len(page_result.records) < page_size:
                    # Last page reached
                    break

                offset += page_size
                await asyncio.sleep(self.delay_between_requests)

        return SocrataFetchResult(
            domain=domain,
            dataset_id=dataset_id,
            is_modified=True,
            status_code=200,
            etag=final_etag,
            records=all_records,
            total_records=len(all_records),
        )
