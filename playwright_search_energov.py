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

        # Capture outgoing requests
        async def on_request(req):
            if "api" in req.url:
                print(f"\n>>> [OUTGOING {req.method}] {req.url}")
                if req.post_data:
                    print(f"Payload: {req.post_data}\n")
        page.on("request", on_request)

        # Capture responses
        async def on_response(res):
            if "api" in res.url:
                print(f"\n<<< [INCOMING RESP {res.status}] {res.url}")
                try:
                    text = await res.text()
                    print("Body preview:", text[:600])
                    if "Result" in text and len(text) > 200:
                        with open("intercepted_live_search.json", "w", encoding="utf-8") as f:
                            f.write(text)
                except Exception as e:
                    pass
        page.on("response", on_response)

        target_url = "https://egov.addisontx.gov/energov_prod/selfservice#/permits"
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

        print("Initializing scope.vm.model and triggering search...")
        result = await page.evaluate('''() => {
            const form = document.getElementById("permitSearchForm");
            if (!form) return "form not found";
            const scope = angular.element(form).scope();
            if (!scope || !scope.vm) return "scope not found";
            
            if (!scope.vm.model) {
                scope.vm.model = {};
            }
            
            // Look for Roof type in secondaryData.PermitTypes
            const types = scope.vm.secondaryData.PermitTypes || [];
            const roofType = types.find(t => t.PermitTypeName && t.PermitTypeName.toLowerCase().includes("roof"));
            if (roofType) {
                scope.vm.selectedType = roofType;
                scope.vm.model.PMPermitTypeId = roofType.PermitTypeId;
            }
            
            scope.vm.model.PageNumber = 1;
            scope.vm.model.PageSize = 25;
            scope.vm.model.SearchMyPermitsOnly = false;
            
            scope.vm.search();
            return {
                model: scope.vm.model,
                selectedType: scope.vm.selectedType ? scope.vm.selectedType.PermitTypeName : null
            };
        }''')
        print("Search triggered with:", json.dumps(result, indent=2))

        print("Waiting for network search response...")
        await page.wait_for_timeout(15000)

        # Check scope results
        scope_results = await page.evaluate('''() => {
            const form = document.getElementById("permitSearchForm");
            if (!form) return null;
            const scope = angular.element(form).scope();
            if (!scope || !scope.vm) return null;
            return {
                totalFound: scope.vm.totalFound,
                totalPages: scope.vm.totalPages,
                searchResultsCount: (scope.vm.searchResults || []).length,
                searchResults: scope.vm.searchResults ? scope.vm.searchResults.slice(0, 5) : []
            };
        }''')
        print("\nScope search results:")
        print(json.dumps(scope_results, indent=2))

        await browser.close()
        print("Done.")

if __name__ == "__main__":
    asyncio.run(run())
