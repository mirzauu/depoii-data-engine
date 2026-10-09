import httpx

def check_market_shares():
    try:
        resp = httpx.get("http://127.0.0.1:8000/api/v1/contractors/leaderboard?jurisdiction=Addison&limit=5", timeout=10.0)
        data = resp.json()
        rankings = data.get("leaderboard", [])
        
        print("\nTop 5 Contractors by Market Share (Addison, TX):")
        for r in rankings:
            print(f"- {r.get('canonicalName')}: {r.get('marketSharePct')}% (Valuation: {r.get('totalValuationFormatted')})")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    check_market_shares()
