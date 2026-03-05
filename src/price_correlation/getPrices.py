import sys
import pandas as pd
from datetime import datetime, timedelta, timezone
from pycoingecko import CoinGeckoAPI
import time

class CryptoPriceFetcher:
    # Use cg.get_coins_list() or https://www.coingecko.com/en/api to find exact IDs
    COIN_ID_MAPPING = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "JLP": "jupiter-perpetuals-liquidity-provider-token",
    }

    def __init__(self, token1: str, token2: str):
        self.cg = CoinGeckoAPI()
        self.token1 = token1.upper()
        self.token2 = token2.upper()
        
        # Resolve to CoinGecko ID
        self.id1 = self.COIN_ID_MAPPING.get(self.token1, self.token1.lower().replace(" ", "-"))
        self.id2 = self.COIN_ID_MAPPING.get(self.token2, self.token2.lower().replace(" ", "-"))
        
        self.name1 = self.token1
        self.name2 = self.token2

    def fetch_and_save(self):
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=360)

        print(f"Fetching 1-year daily prices (UTC) for {self.name1} and {self.name2} vs USD...")
        print(f"Period: {start_dt.date()} → {end_dt.date()}")

        def get_daily_prices(coin_id: str) -> pd.Series:
            try:
                data = self.cg.get_coin_market_chart_range_by_id(
                    id=coin_id,
                    vs_currency="usd",
                    from_timestamp=int(start_dt.timestamp()),
                    to_timestamp=int(end_dt.timestamp()),
                    # No interval → auto = daily for >90 days
                )
                # prices = [[unix_ms, price], ...]
                df = pd.DataFrame(data["prices"], columns=["timestamp_ms", "price"])
                df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms").dt.normalize()  # to date only
                series = df.set_index("date")["price"].rename(coin_id)
                return series
            except Exception as e:
                raise ValueError(f"Failed to fetch {coin_id}: {e}\nCheck coin ID at https://api.coingecko.com/api/v3/coins/list")

        try:
            time.sleep(1.2)  # Gentle on rate limits
            prices1 = get_daily_prices(self.id1)
            time.sleep(1.2)
            prices2 = get_daily_prices(self.id2)

            # Combine on date index (inner join to drop mismatches)
            df = pd.concat([prices1, prices2], axis=1).dropna()
            df.columns = [self.name1, self.name2]

            # Optional: add ratio column if this is a pair
            # df[f"{self.name1}/{self.name2}"] = df[self.name1] / df[self.name2]

            print(f"\n✅ Downloaded {len(df):,} daily data points")
            print(df.tail(8))  # Show recent for verification

            filename = f"{self.name1}_{self.name2}_coingecko_daily_1y.csv"
            df.to_csv(filename)
            print(f"\n💾 Saved to: {filename}")

        except Exception as e:
            print(f"Error during fetch: {e}")
            print("Common fixes: Wrong coin ID? Rate limit? Try again later or add demo_api_key.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python getPrices_coingecko.py <token1> <token2>")
        print("Examples:")
        print("  python getPrices_coingecko.py btc eth")
        print("  python getPrices_coingecko.py sol fart")
        print("  python getPrices_coingecko.py uni pump")
        sys.exit(1)

    token1, token2 = sys.argv[1], sys.argv[2]
    fetcher = CryptoPriceFetcher(token1, token2)
    fetcher.fetch_and_save()
