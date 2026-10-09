import asyncio
from playwright.async_api import async_playwright

DALLASNOW_URL = "https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building"

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(DALLASNOW_URL, wait_until="domcontentloaded", timeout=50000)
        await page.wait_for_selector("select[id*='ddlGSPermitType']", timeout=30000)
        await page.select_option("select[id*='ddlGSPermitType']", "Building/Residential/Roofing/NA")
        await page.click("a[id*='btnNewSearch']")
        print("Waiting for results...")
        await page.wait_for_selector("a[id*='btnExport'], span[id*='lblNoRecord']", timeout=60000)
        await asyncio.sleep(2)
        btn = await page.query_selector("a[id*='btnExport']")
        if btn:
            print("Exporting...")
            async with page.expect_download(timeout=90000) as dl_info:
                await btn.click()
            dl = await dl_info.value
            await dl.save_as("test_res_roof.csv")
            print("Successfully exported test_res_roof.csv")
        else:
            print("No export button found")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check())
