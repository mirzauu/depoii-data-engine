import asyncio
from playwright.async_api import async_playwright

DALLASNOW_URL = "https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building"

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to DallasNow...")
        await page.goto(DALLASNOW_URL, wait_until="networkidle", timeout=35000)
        
        print("Filling form...")
        await page.select_option("select[id*='ddlGSPermitType']", "Building/Commercial/Alteration Addition/NA")
        await page.fill("input[id*='txtGSStartDate']", "10/01/2024")
        await page.fill("input[id*='txtGSEndDate']", "12/31/2024")
        
        print("Submitting search...")
        await page.click("a[id*='btnNewSearch']")
        await page.wait_for_load_state("networkidle", timeout=35000)
        await asyncio.sleep(3)
        
        # Check text on page
        msgs = await page.query_selector_all("span[id*='lbl'], div.aca_notice, div.aca_error")
        for m in msgs:
            txt = (await m.inner_text()).strip()
            if txt:
                print(f"Notice/Message: {txt}")
                
        grid = await page.query_selector("table[id*='gdvPermitList']")
        print(f"Grid present: {grid is not None}")
        
        btn = await page.query_selector("a[id*='btnExport']")
        print(f"Export btn present: {btn is not None}")
        
        pagination = await page.query_selector("td.aca_pagination_td")
        if pagination:
            print("Pagination text:", (await pagination.inner_text()).strip().replace("\n", " "))
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check())
