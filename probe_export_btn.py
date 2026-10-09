import asyncio
from playwright.async_api import async_playwright

DALLASNOW_URL = "https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building"

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(DALLASNOW_URL, wait_until="networkidle", timeout=35000)
        await page.select_option("select[id*='ddlGSPermitType']", "Building/Commercial/Roofing/NA")
        await page.click("a[id*='btnNewSearch']")
        await page.wait_for_load_state("networkidle", timeout=35000)
        await asyncio.sleep(2)
        btn = await page.query_selector("a[id*='btnExport']")
        if btn:
            href = await btn.get_attribute("href")
            onclick = await btn.get_attribute("onclick")
            outer = await btn.evaluate("el => el.outerHTML")
            print("Href:", href)
            print("Onclick:", onclick)
            print("OuterHTML:", outer)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check())
