import requests
import pandas as pd
from typing import Optional

class GeckoTopMemecoins:
    """
    A clean, reusable class to fetch the top 100 memecoins from CoinGecko.
    Maintains exact same behavior as the previous functional version.
    """
    def __init__(self):
        print("🔑 CoinGecko Top 100 Memecoins Fetcher")
        self.api_key: Optional[str] = self._prompt_api_key()
        self.headers = self._setup_headers()
        self.filename = "gecko_top_100_memecoins.csv"
        self.df: Optional[pd.DataFrame] = None

    def _prompt_api_key(self) -> Optional[str]:
        """Prompt user for CoinGecko demo key at startup."""
        key = input("Enter your free CoinGecko API key (demo key): ").strip()
        return key if key else None

    def _setup_headers(self) -> dict:
        """Set up headers with your key or fall back to public API."""
        if not self.api_key:
            print("⚠️ No key entered. Falling back to public API (may be rate-limited).")
            return {}
        return {"x-cg-demo-api-key": self.api_key}

    def fetch(self) -> pd.DataFrame:
        """Fetch top 100 memecoins using CoinGecko /coins/markets endpoint."""
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

        response = requests.get(url, params=params, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Successfully fetched {len(data)} memecoins!")
            self.df = pd.DataFrame(data)
            return self.df
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            self.df = pd.DataFrame()
            return self.df

    def print_top_10(self) -> None:
        """Print nicely formatted top 10 memecoins."""
        if self.df is not None and not self.df.empty:
            print("\n🏆 TOP 10 MEMECOINS")
            cols = ["market_cap_rank", "name", "symbol", "current_price", 
                    "market_cap", "price_change_percentage_24h"]
            print(self.df[cols].head(10).to_string(index=False))

    def print_stats(self) -> None:
        """Print quick summary statistics."""
        if self.df is not None and not self.df.empty:
            print(f"\n📊 Quick Stats:")
            print(f"   Total market cap of top 100: ${self.df['market_cap'].sum():,.0f}")
            print(f"   Avg 24h change: {self.df['price_change_percentage_24h'].mean():.2f}%")

    def save(self) -> None:
        """Save the full DataFrame to CSV using your requested filename."""
        if self.df is not None and not self.df.empty:
            self.df.to_csv(self.filename, index=False)
            print(f"\n💾 Saved full list to {self.filename}")

    def run(self) -> None:
        """Run the complete process — exactly the same flow as before."""
        self.fetch()
        if self.df is not None and not self.df.empty:
            self.print_top_10()
            self.save()
            self.print_stats()


# ==================== USAGE (unchanged) ====================
if __name__ == "__main__":
    fetcher = GeckoTopMemecoins()
    fetcher.run()
