import asyncio
from playwright.async_api import async_playwright

DALLASNOW_URL = "https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building"

async def check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        print("Navigating to DallasNow...")
        await page.goto(DALLASNOW_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_selector("select[id*='ddlGSPermitType']", timeout=30000)
        
        print("Selecting Alteration Addition and filling dates...")
        await page.select_option("select[id*='ddlGSPermitType']", "Building/Commercial/Alteration Addition/NA")
        await page.fill("input[id*='txtGSStartDate']", "10/01/2024")
        await page.fill("input[id*='txtGSEndDate']", "12/31/2024")
        
        await page.click("a[id*='btnNewSearch']")
        print("Waiting for results grid...")
        await page.wait_for_selector("a[id*='btnExport'], span[id*='lblNoRecord']", timeout=60000)
        await asyncio.sleep(2)
        
        btn = await page.query_selector("a[id*='btnExport']")
        if not btn:
            print("No export button found!")
            await browser.close()
            return
            
        print("Triggering download with 90s timeout...")
        try:
            async with page.expect_download(timeout=90000) as dl_info:
                await btn.click()
            dl = await dl_info.value
            await dl.save_as("test_alt_exported.csv")
            print("Successfully exported test_alt_exported.csv!")
        except Exception as e:
            print("Download failed or timed out:", e)
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(check())
