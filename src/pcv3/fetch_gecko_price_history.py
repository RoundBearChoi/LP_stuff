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
# =============================================


class CoinGeckoPriceFetcher:
    """CoinGecko hourly price history downloader with full gap detection."""

    def __init__(self, volume_file: str = VOLUME_TOKENS_FILE):
        self.volume_file = volume_file

    def get_masked_input(self, prompt: str) -> str:
        """Linux-only masked input that prints * for every character.
        (Windows code has been completely removed for simplicity & reliability.)"""
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
        """Load symbol → coingecko_id from your volume tokens file (primary source)."""
        if not os.path.exists(self.volume_file):
            print(f"⚠️  {self.volume_file} not found. Cannot proceed without mapping file.")
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
            print(f"✅ Loaded {len(mapping):,} accurate token mappings from {self.volume_file}")
            return mapping
        except Exception as e:
            print(f"⚠️  Could not load {self.volume_file}: {e}")
            sys.exit(1)

    def get_coin_id(self, symbol: str, volume_mapping: dict) -> str:
        """Resolve symbol to CoinGecko ID — STRICTLY from volume mapping only."""
        symbol_lower = symbol.strip().lower()
        if symbol_lower.startswith("$"):
            symbol_lower = symbol_lower[1:]

        if symbol_lower in volume_mapping:
            cg_id = volume_mapping[symbol_lower]
            print(f"  → Found in volume tokens: {symbol} → {cg_id}")
            return cg_id

        print(f"❌ Token '{symbol}' not found in volume token mapping.")
        print("   Download aborted — please add the token to volume_tokens_whole_list_mar_31st.txt")
        sys.exit(1)

    def fetch_price_history(self, coin_id: str, api_key: str, start_unix: int, end_unix: int | None = None) -> pd.DataFrame:
        """Fetch hourly prices for a specific time range."""
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
            volume_mapping: dict | None = None) -> bool:
        """Main execution logic. Returns True if CSV was created/updated, False if coin not found."""
        
        # Use pre-loaded mapping if provided (batch mode), otherwise load once
        if volume_mapping is None:
            volume_mapping = self.load_volume_token_mapping()
        else:
            print(f"   → Using pre-loaded volume mapping ({len(volume_mapping):,} tokens)")

        # API key input (only if none was passed from batch)
        if api_key is None:
            print("\nEnter your CoinGecko Pro API key (will be shown as *):")
            api_key = self.get_masked_input("API Key: ")
            if not api_key:
                print("Error: API key is required.")
                sys.exit(1)

        coin_id = self.get_coin_id(coin_input, volume_mapping)
        print(f"Using CoinGecko ID: {coin_id} (file will be named with your input '{coin_input}')")

        os.makedirs("price_data", exist_ok=True)
        filename = f"price_data/gecko_{coin_input}_hourly_price_history.csv"

        if os.path.exists(filename):
            existing_df = pd.read_csv(filename)
            existing_df["timestamp"] = pd.to_datetime(existing_df["timestamp"], format='mixed')
            print(f"Loaded existing CSV with {len(existing_df):,} records.")
        else:
            existing_df = pd.DataFrame(columns=["timestamp", "price_usd"])
            print("No existing CSV – will create full history file.")

        # === FULL WINDOW CALCULATION ===
        now = datetime.now()
        end_unix = int(time.time())
        days_back = months * 30.5 + 2
        required_start = now - timedelta(days=days_back)
        required_start_unix = int(required_start.timestamp())

        # === FIND ALL MISSING RANGES ===
        missing_ranges = []
        if existing_df.empty:
            missing_ranges.append((required_start_unix, end_unix))
        else:
            df_sorted = existing_df.sort_values("timestamp").reset_index(drop=True)
            current_earliest_unix = int(df_sorted["timestamp"].iloc[0].timestamp())
            current_latest_unix = int(df_sorted["timestamp"].iloc[-1].timestamp())

            if current_earliest_unix > required_start_unix:
                missing_ranges.append((required_start_unix, current_earliest_unix))

            for i in range(1, len(df_sorted)):
                prev_ts = int(df_sorted["timestamp"].iloc[i-1].timestamp())
                curr_ts = int(df_sorted["timestamp"].iloc[i].timestamp())
                if curr_ts - prev_ts > 3600 * 2:
                    missing_ranges.append((prev_ts + 3600, curr_ts))

            if current_latest_unix < end_unix - 3600:
                missing_ranges.append((current_latest_unix + 3600, end_unix))

            if not missing_ranges:
                print("✅ CSV already covers the full requested window and is up-to-date.")
                print(f"   Data saved to {filename} ({len(existing_df):,} rows).")
                sys.exit(0)

        print(f"→ Found {len(missing_ranges)} missing range(s) to fetch.")

        # === FETCH ALL MISSING RANGES ===
        new_dfs = []
        for start_u, end_u in missing_ranges:
            print(f"\nFetching missing range: {datetime.fromtimestamp(start_u)} → {datetime.fromtimestamp(end_u)}")
            chunk_df = self.fetch_price_history(coin_id, api_key, start_unix=start_u, end_unix=end_u)
            if not chunk_df.empty:
                new_dfs.append(chunk_df)

        # === MERGE EVERYTHING ===
        if new_dfs:
            combined_df = pd.concat([existing_df] + new_dfs, ignore_index=True)
        else:
            combined_df = existing_df

        combined_df = combined_df.drop_duplicates(subset=["timestamp"])
        combined_df = combined_df.sort_values("timestamp").reset_index(drop=True)

        if len(combined_df) == 0:
            print(f"\n❌ Coin not found on CoinGecko (404).")
            print(f"   No CSV created for {coin_input}.")
            print("   This usually means the coingecko_id in your mapping file is outdated.")
            return False

        combined_df.to_csv(filename, index=False)

        print(f"\n✅ Success! Full {months} months of data (with all gaps filled):")
        print(f"   Saved {len(combined_df):,} hourly records to {filename}")
        print(f"   Date range: {combined_df['timestamp'].min()} → {combined_df['timestamp'].max()}")
        print(f"   Latest price: ${combined_df['price_usd'].iloc[-1]:.2f} USD")
        return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fetch_gecko_price_history.py <coin> <months>")
        print("Example: python fetch_gecko_price_history.py btc 2")
        sys.exit(1)

    coin_input = sys.argv[1].strip()
    months = int(sys.argv[2])

    fetcher = CoinGeckoPriceFetcher()
    fetcher.run(coin_input, months)
