import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    print("Launching Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors", "--no-sandbox"]
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Monitor requests and responses
        page.on("request", lambda req: print(f"[REQ] {req.method} {req.url}") if "api" in req.url else None)
        
        async def on_response(res):
            if "api" in res.url and res.request.method == "POST":
                print(f"\n[RESP POST] {res.url} -> HTTP {res.status}")
                try:
                    text = await res.text()
                    print("Response body preview:", text[:600])
                except Exception as e:
                    print("Could not read body:", e)

        page.on("response", on_response)

        target_url = "https://egov.addisontx.gov/energov_prod/selfservice#/permits"
        print(f"Navigating to {target_url} ...")
        try:
            await page.goto(target_url, wait_until="networkidle", timeout=45000)
        except Exception as e:
            print("Goto warning/timeout:", e)

        print("Page title:", await page.title())
        await page.wait_for_timeout(3000)

        # Look for search button
        buttons = await page.query_selector_all("button")
        print(f"Found {len(buttons)} buttons.")
        search_btn = None
        for b in buttons:
            text = (await b.inner_text()).strip()
            print(f"Button text: '{text}'")
            if "search" in text.lower():
                search_btn = b
                break

        if search_btn:
            print("Clicking Search button...")
            await search_btn.click()
            await page.wait_for_timeout(6000)
        else:
            print("No Search button found by text. Looking for submit or input[type=submit]...")

        await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(run())
