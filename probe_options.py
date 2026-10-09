import asyncio
from playwright.async_api import async_playwright

DALLASNOW_URL = "https://aca-prod.accela.com/DALLASTX/Cap/CapHome.aspx?module=Building"

async def get_options():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(DALLASNOW_URL, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_selector("select[id*='ddlGSPermitType']", timeout=30000)
        opts = await page.eval_on_selector_all("select[id*='ddlGSPermitType'] option", "els => els.map(e => ({text: e.innerText, val: e.value}))")
        for o in opts:
            if "commercial" in o["text"].lower() or "roof" in o["text"].lower():
                print(f"{o['val']} -> {o['text']}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(get_options())
