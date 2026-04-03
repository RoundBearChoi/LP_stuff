#!/usr/bin/env python3
"""
fetch_gecko_price_history.py
Fetches hourly price history from CoinGecko Pro API for any token.
Usage: python fetch_gecko_price_history.py <symbol> [months]
Example: python fetch_gecko_price_history.py btc 24
"""

import sys
import os
import time
import pandas as pd
from datetime import datetime, timedelta, timezone   # ← timezone added
import requests
import termios
import tty

# ==================== CONFIG SECTION ====================
CONFIG = {
    "output_dir": "fetched_data",
    "force_fresh_download": True,      # ← Change to True to always re-download
    "vs_currency": "usd",
    "chunk_days": 90,                   # Safe max for hourly data on paid plans
    "top_tokens_file": "top_tokens_by_market_cap.csv",
    "sleep_between_calls": 1.2,         # Polite rate-limit cushion
}
# =======================================================

def get_masked_input(prompt="Enter your CoinGecko Pro API key: "):
    """Linux-only masked input that shows * for every character (including paste)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        print(prompt, end='', flush=True)
        password = ""
        while True:
            ch = sys.stdin.read(1)
            if ch in ('\n', '\r'):
                print()
                break
            elif ch == '\x7f':  # Backspace
                if password:
                    password = password[:-1]
                    print('\b \b', end='', flush=True)
            else:
                password += ch
                print('*', end='', flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return password

def main():
    if len(sys.argv) < 2:
        print("Usage: python fetch_gecko_price_history.py <symbol> [months]")
        print("Example: python fetch_gecko_price_history.py btc 24")
        sys.exit(1)

    symbol = sys.argv[1].lower().strip()
    months = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    # === Prompt for API key (masked) ===
    print("\n=== CoinGecko Hourly Price History Fetcher ===")
    api_key = get_masked_input()
    if not api_key.strip():
        print("Error: API key cannot be empty.")
        sys.exit(1)

    # === Setup output file ===
    os.makedirs(CONFIG["output_dir"], exist_ok=True)
    output_file = os.path.join(CONFIG["output_dir"], f"{symbol}_price_history.csv")

    # === Skip if file already exists (unless force_fresh_download=True) ===
    if os.path.exists(output_file) and not CONFIG["force_fresh_download"]:
        print(f"✅ {output_file} already exists.")
        print("   (Set force_fresh_download=True in the config section to override)")
        sys.exit(0)

    # === Load symbol → ID mapping ===
    if not os.path.exists(CONFIG["top_tokens_file"]):
        print(f"Error: {CONFIG['top_tokens_file']} not found!")
        print("   Make sure the file is in the same folder as this script.")
        sys.exit(1)

    tokens_df = pd.read_csv(CONFIG["top_tokens_file"])
    # Case-insensitive match on 'symbol' column
    token_row = tokens_df[tokens_df['symbol'].str.lower() == symbol]
    if token_row.empty:
        print(f"Error: Symbol '{symbol}' not found in {CONFIG['top_tokens_file']}")
        print("   First 20 symbols in file:", tokens_df['symbol'].str.lower().head(20).tolist())
        sys.exit(1)

    coin_id = token_row.iloc[0]['id']
    print(f"✅ Mapped {symbol.upper()} → CoinGecko ID: {coin_id}")

    # === Calculate date range (approx months) — now timezone-aware ===
    end_date = datetime.now(timezone.utc)          # ← UTC-aware
    start_date = end_date - timedelta(days=int(months * 30.44))

    print(f"Fetching ≈{months} months of **hourly** USD prices for {symbol.upper()}")
    print(f"   Range (UTC): {start_date.date()} → {end_date.date()}")

    all_data = []

    # === Chunked fetching (required for hourly data > ~100 days) ===
    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=CONFIG["chunk_days"]), end_date)

        from_ts = int(current_start.timestamp())
        to_ts = int(current_end.timestamp())

        url = f"https://pro-api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"
        params = {
            "vs_currency": CONFIG["vs_currency"],
            "from": from_ts,
            "to": to_ts,
            "interval": "hourly",
        }
        headers = {"x-cg-pro-api-key": api_key}

        print(f"  → Fetching chunk: {current_start.date()} to {current_end.date()} (UTC)")

        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                prices = data.get("prices", [])
                for ts_ms, price in prices:
                    # ← This is the key change: now UTC-aware
                    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    all_data.append({"datetime": dt, "price_usd": price})
            else:
                print(f"  ⚠️  Error {response.status_code}: {response.text[:300]}")
                if response.status_code == 429:
                    print("   Rate limit hit — waiting 10s...")
                    time.sleep(10)
        except Exception as e:
            print(f"  ❌ Request failed: {e}")

        current_start = current_end
        time.sleep(CONFIG["sleep_between_calls"])

    # === Save to CSV ===
    if not all_data:
        print("❌ No data received.")
        sys.exit(1)

    df = pd.DataFrame(all_data)
    df = df.drop_duplicates(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    df["price_usd"] = df["price_usd"].round(8)

    # Ensure pandas recognizes it as proper tz-aware datetime (extra safety)
    df["datetime"] = pd.to_datetime(df["datetime"])

    df.to_csv(output_file, index=False)

    print(f"\n🎉 SUCCESS! Saved {len(df):,} hourly price points")
    print(f"   File: {output_file}")
    print(f"   Date range (UTC): {df['datetime'].min().date()} → {df['datetime'].max().date()}")
    print(f"   Timezone: {df['datetime'].iloc[0].tzinfo}  ← now UTC-aware!")
    print(f"   File size: {os.path.getsize(output_file) / 1024:.1f} KB")
    print(f"   Columns: datetime (UTC-aware), price_usd")

if __name__ == "__main__":
    main()
