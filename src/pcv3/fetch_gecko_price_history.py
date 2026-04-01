import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# =============================================
# CONFIGURATION
# =============================================
VOLUME_TOKENS_FILE = "volume_tokens_whole_list_mar_31st.txt"
FORCE_FRESH_DOWNLOAD = False
# =============================================


class CoinGeckoPriceFetcher:
    """Simplified CoinGecko hourly price history downloader – no gap filling."""

    def __init__(self, volume_file: str = VOLUME_TOKENS_FILE):
        self.volume_file = volume_file

    def get_masked_input(self, prompt: str) -> str:
        """Linux-only masked input (prints * for every character)."""
        print(prompt, end="", flush=True)
        key = ""

        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\n", "\r"):
                    print()
                    break
                elif ch == "\x7f":          # Backspace
                    if key:
                        key = key[:-1]
                        print("\b \b", end="", flush=True)
                else:
                    key += ch
                    print("*", end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        return key.strip()

    def load_volume_token_mapping(self) -> dict:
        """Load symbol → coingecko_id mapping (primary source)."""
        if not os.path.exists(self.volume_file):
            print(f"⚠️  {self.volume_file} not found.")
            sys.exit(1)

        try:
            df = pd.read_csv(self.volume_file)
            mapping = {}
            for _, row in df.iterrows():
                raw_symbol = str(row.get("symbol", "")).strip()
                cg_id = str(row.get("coingecko_id", "")).strip()
                if raw_symbol and cg_id:
                    symbol = raw_symbol.lower()
                    if symbol.startswith("$"):
                        symbol = symbol[1:]
                    mapping[symbol] = cg_id
            print(f"✅ Loaded {len(mapping):,} token mappings from {self.volume_file}")
            return mapping
        except Exception as e:
            print(f"⚠️  Could not load mapping: {e}")
            sys.exit(1)

    def get_coin_id(self, symbol: str, volume_mapping: dict) -> str:
        """Resolve symbol to CoinGecko ID (strictly from volume mapping)."""
        symbol_lower = symbol.strip().lower()
        if symbol_lower.startswith("$"):
            symbol_lower = symbol_lower[1:]

        if symbol_lower in volume_mapping:
            cg_id = volume_mapping[symbol_lower]
            print(f"  → {symbol} → {cg_id}")
            return cg_id

        print(f"❌ Token '{symbol}' not found in mapping.")
        sys.exit(1)

    def fetch_price_history(self, coin_id: str, api_key: str, start_unix: int, end_unix: int | None = None) -> pd.DataFrame:
        """Fetch hourly prices (still uses safe chunking for long ranges)."""
        if end_unix is None:
            end_unix = int(time.time())

        print(f"Fetching hourly prices from {datetime.fromtimestamp(start_unix)} to {datetime.fromtimestamp(end_unix)}...")

        all_prices = []
        current_from = start_unix
        max_chunk_seconds = 89 * 86400

        while current_from < end_unix:
            current_to = min(current_from + max_chunk_seconds, end_unix)
            print(f"  → Chunk {datetime.fromtimestamp(current_from)} → {datetime.fromtimestamp(current_to)}")

            url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
            headers = {"x-cg-pro-api-key": api_key}
            params = {"vs_currency": "usd", "from": current_from, "to": current_to}

            try:
                response = requests.get(url, headers=headers, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                prices = data.get("prices", [])
                if prices:
                    all_prices.extend(prices)
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    print("Rate limit hit – waiting 60 seconds...")
                    time.sleep(60)
                    continue
                print(f"API error {response.status_code}: {response.text}")
                break
            except Exception as e:
                print(f"Request failed: {e}")
                break

            current_from = current_to + 60
            time.sleep(1.1)

        if not all_prices:
            print("No price data returned from API.")
            return pd.DataFrame(columns=["timestamp", "price_usd"])

        df = pd.DataFrame(all_prices, columns=["timestamp_ms", "price_usd"])
        df["timestamp"] = pd.to_datetime(df["timestamp_ms"], unit="ms")
        df = df[["timestamp", "price_usd"]]
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        print(f"  → Fetched {len(df):,} hourly records.")
        return df

    def run(self, coin_input: str, months: int, api_key: str | None = None,
            volume_mapping: dict | None = None) -> tuple[bool, bool]:
        """Main entry point – returns (success: bool, fetched: bool).
        `fetched` is True only when we actually made API calls (so the batch script knows whether to wait)."""
        if volume_mapping is None:
            volume_mapping = self.load_volume_token_mapping()
        else:
            print(f"   → Using pre-loaded volume mapping ({len(volume_mapping):,} tokens)")

        if api_key is None:
            print("\nEnter your CoinGecko Pro API key (masked):")
            api_key = self.get_masked_input("API Key: ")
            if not api_key:
                print("❌ API key is required.")
                sys.exit(1)

        coin_id = self.get_coin_id(coin_input, volume_mapping)
        print(f"Using CoinGecko ID: {coin_id} (file will be named with '{coin_input}')")

        os.makedirs("price_data", exist_ok=True)
        filename = f"price_data/gecko_{coin_input}_hourly_price_history.csv"

        # === SIMPLE SKIP LOGIC ===
        if os.path.exists(filename) and not FORCE_FRESH_DOWNLOAD:
            print(f"⏭️  {coin_input}: File already exists → skipping download")
            print(f"    (Set FORCE_FRESH_DOWNLOAD=True in fetch_gecko_price_history.py to force refresh)")
            return True, False   # success, but did NOT hit the API

        if os.path.exists(filename):
            print(f"🔄 {coin_input}: FORCE_FRESH_DOWNLOAD=True → overwriting existing file with fresh data")

        # === ALWAYS DOWNLOAD FULL FRESH HISTORY ===
        days_back = months * 30.5 + 2
        start_unix = int((datetime.now() - timedelta(days=days_back)).timestamp())
        end_unix = int(time.time())

        print(f"📥 Downloading fresh {months} month(s) of hourly data for {coin_input}...")

        df = self.fetch_price_history(coin_id, api_key, start_unix, end_unix)

        if df.empty:
            print(f"❌ No data returned for {coin_input} (coin may not exist on CoinGecko)")
            return False, True   # attempted fetch, so we still count it as "used API"

        df.to_csv(filename, index=False)

        print(f"\n✅ Success! Saved {len(df):,} hourly records to {filename}")
        print(f"   Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
        print(f"   Latest price: ${df['price_usd'].iloc[-1]:.4f} USD")
        return True, True        # success AND fetched


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fetch_gecko_price_history.py <coin> <months>")
        print("Example: python fetch_gecko_price_history.py btc 2")
        sys.exit(1)

    coin_input = sys.argv[1].strip()
    months = int(sys.argv[2])

    fetcher = CoinGeckoPriceFetcher()
    fetcher.run(coin_input, months)   # return value ignored for single-coin usage
