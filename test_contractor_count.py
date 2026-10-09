import httpx

def count_contractors():
    try:
        resp = httpx.get("http://127.0.0.1:8000/api/v1/contractors/leaderboard?limit=200", timeout=10.0)
        data = resp.json()
        rankings = data.get("leaderboard", [])
        print(f"Total Unique Contractors: {len(rankings)}")
        
        # Print top 5 to get a feel
        print("\nTop 5 Contractors:")
        for r in rankings[:5]:
            print(f"- {r.get('canonicalName')} (Permits: {r.get('permitCount')})")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    count_contractors()
