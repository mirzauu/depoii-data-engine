import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    print("Launching Chromium for Public Search...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--ignore-certificate-errors", "--no-sandbox"]
        )
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()

        # Monitor requests and responses
        page.on("request", lambda req: print(f"\n>>> [REQ] {req.method} {req.url}\nPayload: {req.post_data}") if "search" in req.url.lower() and req.method == "POST" else None)
        
        async def on_response(res):
            if "search" in res.url.lower() and res.request.method == "POST":
                print(f"\n<<< [RESP] {res.url} -> HTTP {res.status}")
                try:
                    text = await res.text()
                    print("Body preview:", text[:800])
                    if len(text) > 200:
                        with open("public_search_live_response.json", "w", encoding="utf-8") as f:
                            f.write(text)
                except Exception as e:
                    print("Error reading body:", e)

        page.on("response", on_response)

        target_url = "https://egov.addisontx.gov/energov_prod/selfservice#/search"
        print(f"Navigating to {target_url} ...")
        await page.goto(target_url, wait_until="networkidle", timeout=45000)

        # Handle modal
        modal = await page.query_selector("#globalMessageDialog")
        if modal:
            btn = await modal.query_selector("button")
            if btn:
                print("Closing modal...")
                await btn.click()
                await page.wait_for_timeout(1000)

        print("Page Title:", await page.title())

        # Type 'roof' in the search box
        search_input = await page.query_selector("#SearchKeyword input, input#SearchKeyword, input[search-box-id=SearchKeyword], #SearchKeyword")
        if not search_input:
            search_input = await page.query_selector("input[type=text]")

        if search_input:
            print("Found search input! Typing 'roof'...")
            await search_input.fill("roof")
            await page.wait_for_timeout(1000)
            await search_input.press("Enter")
        else:
            print("Could not find search input. Checking via Angular scope...")

        # Also look for the Search button
        buttons = await page.query_selector_all("button")
        for b in buttons:
            txt = (await b.inner_text()).strip()
            if "search" in txt.lower():
                print(f"Clicking button: '{txt}'")
                await b.click()
                break

        print("Waiting for search results...")
        await page.wait_for_timeout(15000)

        await page.screenshot(path="public_search_screenshot.png")
        print("Screenshot saved to public_search_screenshot.png")

        await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(run())
