#!/usr/bin/env python3
"""
fetch_gecko_price_history.py

Updated version:
- Uses volume_tokens_whole_list_mar_31st.txt as PRIMARY mapping source
- Configurable filename at the top
- Cross-platform masked API key input (shows * on Windows + Linux/WSL)
"""

import sys
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta

# =============================================
# CONFIGURATION
# =============================================
# Change this if you rename/move the volume file in the future
VOLUME_TOKENS_FILE = "volume_tokens_whole_list_mar_31st.txt"
# =============================================


def get_masked_input(prompt: str) -> str:
    """Cross-platform masked input that prints * for every character."""
    print(prompt, end="", flush=True)
    key = ""

    if os.name == "nt":  # Windows
        import msvcrt
        while True:
            ch = msvcrt.getch()
            if ch in (b"\r", b"\n"):  # Enter
                print()
                break
            elif ch == b"\x08":  # Backspace
                if key:
                    key = key[:-1]
                    print("\b \b", end="", flush=True)
            else:
                key += ch.decode("utf-8", errors="ignore")
                print("*", end="", flush=True)
    else:  # Linux / macOS / WSL
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
                elif ch == "\x7f":  # Backspace
                    if key:
                        key = key[:-1]
                        print("\b \b", end="", flush=True)
                else:
                    key += ch
                    print("*", end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return key.strip()


def load_volume_token_mapping(filename: str) -> dict:
    """Load symbol → coingecko_id from your volume tokens file (primary source)."""
    if not os.path.exists(filename):
        print(f"⚠️  {filename} not found. Will fall back to CoinGecko public list only.")
        return {}

    try:
        df = pd.read_csv(filename)
        mapping = {}
        for _, row in df.iterrows():
            raw_symbol = str(row.get("symbol", "")).strip()
            cg_id = str(row.get("coingecko_id", "")).strip()
            if raw_symbol and cg_id:
                # Normalize: remove leading $ and lowercase
                symbol = raw_symbol.lower()
                if symbol.startswith("$"):
                    symbol = symbol[1:]
                mapping[symbol] = cg_id
        print(f"✅ Loaded {len(mapping):,} accurate token mappings from {filename}")
        return mapping
    except Exception as e:
        print(f"⚠️  Could not load {filename}: {e}")
        return {}


def get_coin_id(symbol: str, volume_mapping: dict) -> str:
    """Resolve symbol to CoinGecko ID with new priority order."""
    symbol_lower = symbol.strip().lower()
    if symbol_lower.startswith("$"):
        symbol_lower = symbol_lower[1:]

    # 1. PRIMARY: your volume tokens file (most reliable)
    if symbol_lower in volume_mapping:
        cg_id = volume_mapping[symbol_lower]
        print(f"  → Found in volume tokens: {symbol} → {cg_id}")
        return cg_id

    # 2. Fallback: original CoinGecko public list
    print(f"  → Not in volume list, checking CoinGecko public list for '{symbol}'...")
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        coins = response.json()
        for coin in coins:
            if coin.get("symbol", "").lower() == symbol_lower:
                return coin["id"]
    except Exception as e:
        print(f"  Warning: CoinGecko list fetch failed: {e}")

    # 3. Final fallback: assume user gave exact ID
    print(f"  → Symbol not found anywhere, assuming '{symbol}' is already the CoinGecko ID.")
    return symbol_lower


def fetch_price_history(
    coin_id: str,
    api_key: str,
    months: int = 3,
    start_unix: int | None = None,
) -> pd.DataFrame:
    """(Your original function - unchanged)"""
    to_unix = int(time.time())
    if start_unix is None:
        days_back = max(months * 31, 1)
        start_unix = int(time.time() - days_back * 86400)

    print(f"Fetching hourly prices for {coin_id} from {datetime.fromtimestamp(start_unix)} to now...")

    all_prices = []
    current_from = start_unix
    max_chunk_seconds = 89 * 86400

    while current_from < to_unix:
        current_to = min(current_from + max_chunk_seconds, to_unix)
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

    print(f"  → Fetched {len(df):,} new hourly records.")
    return df


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python fetch_gecko_price_history.py <coin> <months>")
        print("Example: python fetch_gecko_price_history.py btc 1")
        sys.exit(1)

    coin_input = sys.argv[1].strip()
    months = int(sys.argv[2])

    # Load the volume tokens mapping (this is the new primary source)
    volume_mapping = load_volume_token_mapping(VOLUME_TOKENS_FILE)

    # API key with * masking (cross-platform)
    print("\nEnter your CoinGecko Basic Tier API key (will be shown as *):")
    api_key = get_masked_input("API Key: ")
    if not api_key:
        print("Error: API key is required.")
        sys.exit(1)

    # Resolve ID (now uses your volume file first!)
    coin_id = get_coin_id(coin_input, volume_mapping)
    print(f"Using CoinGecko ID: {coin_id} (file will be named with your input '{coin_input}')")

    # Setup output
    os.makedirs("price_data", exist_ok=True)
    filename = f"price_data/gecko_{coin_input}_hourly_price_history.csv"

    # Load existing data if any
    if os.path.exists(filename):
        existing_df = pd.read_csv(filename, parse_dates=["timestamp"])
        print(f"Loaded existing CSV with {len(existing_df):,} records (latest: {existing_df['timestamp'].max()}).")
    else:
        existing_df = pd.DataFrame(columns=["timestamp", "price_usd"])
        print("No existing CSV – will create full history file.")

    # Decide fetch start (rest of your original logic)
    now = datetime.now()
    end_unix = int(time.time())
    desired_start = now - timedelta(days=months * 30.5)
    desired_start_unix = int(desired_start.timestamp())

    if not existing_df.empty:
        last_ts = existing_df["timestamp"].max()
        last_unix = int(last_ts.timestamp())
        fetch_start_unix = max(desired_start_unix, last_unix + 3600)
        if fetch_start_unix >= end_unix - 3600:
            print("CSV is already up-to-date (no significant new data).")
            print(f"Data saved to {filename} ({len(existing_df):,} rows).")
            sys.exit(0)
        print(f"Fetching only missing data since {last_ts}...")
    else:
        fetch_start_unix = desired_start_unix
        print(f"Fetching full {months} months of hourly data...")

    new_df = fetch_price_history(coin_id, api_key, months=months, start_unix=fetch_start_unix)

    if new_df.empty:
        print("No new data was fetched.")
        if not existing_df.empty:
            print(f"Existing file unchanged: {filename}")
        sys.exit(0)

    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=["timestamp"])
    combined_df = combined_df.sort_values("timestamp").reset_index(drop=True)

    combined_df.to_csv(filename, index=False)
    print(f"\n✅ Success! Saved {len(combined_df):,} hourly records to {filename}")
    print(f"   Date range: {combined_df['timestamp'].min()} → {combined_df['timestamp'].max()}")
    print(f"   Latest price: ${combined_df['price_usd'].iloc[-1]:.2f} USD")


if __name__ == "__main__":
    main()
