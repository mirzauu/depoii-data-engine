import asyncio
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from bs4 import BeautifulSoup
from app.extraction.config_loader import CityConfig, load_city_config
from app.core.logging import logger


@dataclass
class AccelaScraperResult:
    jurisdiction: str
    records: List[Dict[str, Any]]
    pages_scraped: int
    total_records: int
    status: str  # "SUCCESS" | "FAILED" | "ZERO_ROWS"
    error: Optional[str] = None


def parse_accela_html_table(html: str, config: CityConfig) -> List[Dict[str, Any]]:
    """
    Parses an Accela Citizen Access HTML results table using BeautifulSoup
    and the city's column index mapping.
    """
    soup = BeautifulSoup(html, "html.parser")
    table_selector = config.results.table_selector if config.results else "table"

    # Remove CSS brackets if present e.g. table[id*='gdvPermitList']
    if "[" in table_selector:
        # Match table tag with attribute
        attr_match = re.search(r"table\[([a-zA-Z_-]+)\*=['\"]([^'\"]+)['\"]\]", table_selector)
        if attr_match:
            attr_name, attr_val = attr_match.group(1), attr_match.group(2)
            table = soup.find("table", {attr_name: re.compile(attr_val, re.IGNORECASE)})
        else:
            table = soup.find("table")
    else:
        table = soup.select_one(table_selector)

    if not table:
        return []

    rows = table.find_all("tr")
    if not rows:
        return []

    cols = config.columns
    permit_col = cols.permit_number if cols else 1
    type_col = cols.record_type if cols else 2
    addr_col = cols.address if cols else 3
    date_col = cols.issue_date if cols else 4
    status_col = cols.status if cols else 5
    desc_col = cols.description if cols and cols.description is not None else None

    parsed_records: List[Dict[str, Any]] = []

    for tr in rows:
        tds = tr.find_all(["td", "th"])
        # Skip header or empty rows
        min_required = max(permit_col, type_col, addr_col, date_col, status_col)
        if not tds or len(tds) <= min_required:
            continue

        raw_permit_num = tds[permit_col].get_text(strip=True)
        if not raw_permit_num or raw_permit_num.lower() in ("record number", "permit #", "permit number"):
            continue

        record_type = tds[type_col].get_text(strip=True)
        address = tds[addr_col].get_text(strip=True)
        issue_date = tds[date_col].get_text(strip=True)
        status = tds[status_col].get_text(strip=True)
        description = tds[desc_col].get_text(strip=True) if (desc_col is not None and len(tds) > desc_col) else ""

        parsed_records.append({
            "permit_number": raw_permit_num,
            "record_type": record_type,
            "address": address,
            "issue_date": issue_date,
            "status": status,
            "description": description,
            "jurisdiction": config.jurisdiction,
            "state": config.state,
        })

    return parsed_records


class UniversalAccelaScraper:
    """
    Config-driven Universal Playwright Scraper for Accela Citizen Access (ACA).
    Dynamically loads city-specific DOM selectors, handles disclaimer modals,
    fills search forms, extracts tabular permit data, and traverses pagination.
    """
    def __init__(self, city_key: str, config: Optional[CityConfig] = None):
        self.city_key = city_key
        self.config = config or load_city_config(city_key)

    async def scrape_permits(
        self,
        start_date: str = "01/01/2024",
        end_date: str = "12/31/2026",
        headless: bool = True,
        max_pages: Optional[int] = None,
    ) -> AccelaScraperResult:
        cfg = self.config
        if not cfg.portal:
            return AccelaScraperResult(
                jurisdiction=cfg.jurisdiction,
                records=[],
                pages_scraped=0,
                total_records=0,
                status="FAILED",
                error="City config does not define a portal block",
            )

        limit_pages = max_pages or (cfg.results.max_pages if cfg.results else 10)
        delay_sec = (cfg.anti_bot.request_delay_ms / 1000.0) if cfg.anti_bot else 2.0
        all_records: List[Dict[str, Any]] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return AccelaScraperResult(
                jurisdiction=cfg.jurisdiction,
                records=[],
                pages_scraped=0,
                total_records=0,
                status="FAILED",
                error="Playwright is not installed in the execution environment",
            )

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800},
                    ignore_https_errors=True,
                )
                page = await context.new_page()

                search_url = f"{cfg.portal.base_url.rstrip('/')}/{cfg.portal.search_path.lstrip('/')}"
                logger.info(f"[Accela] Navigating to {search_url} for {cfg.jurisdiction}")

                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(delay_sec)

                # 1. Accept Disclaimer if required
                if cfg.disclaimer and cfg.disclaimer.has_disclaimer:
                    if cfg.disclaimer.checkbox_selector:
                        chk = await page.query_selector(cfg.disclaimer.checkbox_selector)
                        if chk:
                            await chk.check()
                    if cfg.disclaimer.continue_button:
                        btn = await page.query_selector(cfg.disclaimer.continue_button)
                        if btn:
                            await btn.click()
                            await page.wait_for_load_state("domcontentloaded")
                            await asyncio.sleep(delay_sec)

                # 2. Fill Search Form
                if cfg.search_form:
                    if cfg.search_form.date_start_selector:
                        start_el = await page.query_selector(cfg.search_form.date_start_selector)
                        if start_el:
                            await start_el.fill(start_date)
                    if cfg.search_form.date_end_selector:
                        end_el = await page.query_selector(cfg.search_form.date_end_selector)
                        if end_el:
                            await end_el.fill(end_date)
                    if cfg.search_form.keyword_selector:
                        kw_el = await page.query_selector(cfg.search_form.keyword_selector)
                        if kw_el:
                            await kw_el.fill("Roof")

                    # Submit form
                    search_btn = await page.query_selector(cfg.search_form.search_button)
                    if search_btn:
                        await search_btn.click()
                        try:
                            await page.wait_for_load_state("networkidle", timeout=15000)
                        except Exception:
                            await asyncio.sleep(delay_sec)
                        await asyncio.sleep(delay_sec)

                # 3. Pagination & Extraction Loop
                pages_visited = 0
                while pages_visited < limit_pages:
                    pages_visited += 1
                    html = await page.content()
                    page_records = parse_accela_html_table(html, cfg)
                    all_records.extend(page_records)
                    logger.info(f"[Accela] Page {pages_visited}: extracted {len(page_records)} rows for {cfg.jurisdiction}")

                    # Check if next page exists
                    if not cfg.results or not cfg.results.next_page_selector:
                        break

                    next_link = await page.query_selector(cfg.results.next_page_selector)
                    if not next_link:
                        break

                    await next_link.click()
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    await asyncio.sleep(delay_sec)

                await browser.close()

                return AccelaScraperResult(
                    jurisdiction=cfg.jurisdiction,
                    records=all_records,
                    pages_scraped=pages_visited,
                    total_records=len(all_records),
                    status="SUCCESS" if all_records else "ZERO_ROWS",
                )

        except Exception as err:
            logger.error(f"[Accela] Scraper error for {cfg.jurisdiction}: {err}")
            return AccelaScraperResult(
                jurisdiction=cfg.jurisdiction,
                records=all_records,
                pages_scraped=0,
                total_records=len(all_records),
                status="FAILED",
                error=str(err),
            )
