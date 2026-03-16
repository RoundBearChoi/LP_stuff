import requests
import pandas as pd

# ==================== PROMPT FOR API KEY ====================
print("🔑 CoinGecko Top 100 Memecoins Fetcher")
api_key = input("Enter your free CoinGecko API key (demo key): ").strip()

if not api_key:
    print("⚠️ No key entered. Falling back to public API (may be rate-limited).")
    headers = {}
else:
    headers = {"x-cg-demo-api-key": api_key}

# ==================== FETCH TOP 100 MEMECOINS ====================
def get_top_100_memecoins() -> pd.DataFrame:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "category": "meme-token",          # Official Meme category
        "order": "market_cap_desc",
        "per_page": 100,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h"
    }

    response = requests.get(url, params=params, headers=headers)

    if response.status_code == 200:
        data = response.json()
        print(f"✅ Successfully fetched {len(data)} memecoins!")
        return pd.DataFrame(data)
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return pd.DataFrame()

# ==================== RUN IT ====================
if __name__ == "__main__":
    df = get_top_100_memecoins()

    if not df.empty:
        # Pretty print top 10
        print("\n🏆 TOP 10 MEMECOINS")
        print(df[["market_cap_rank", "name", "symbol", "current_price", 
                  "market_cap", "price_change_percentage_24h"]].head(10).to_string(index=False))

        # === YOUR REQUESTED FILENAME ===
        filename = "gecko_top_100_memecoins.csv"
        df.to_csv(filename, index=False)
        print(f"\n💾 Saved full list to {filename}")
        
        # Quick stats
        print(f"\n📊 Quick Stats:")
        print(f"   Total market cap of top 100: ${df['market_cap'].sum():,.0f}")
        print(f"   Avg 24h change: {df['price_change_percentage_24h'].mean():.2f}%")
