#!/usr/bin/env python3
"""
fetch_exchange_info.py
Simple CoinGecko exchange data fetcher.
Usage: python fetch_exchange_info.py <exchange_id>
Example: python fetch_exchange_info.py uniswap-v2-abstract
"""

import sys
import requests
import json
from datetime import datetime

def fetch_exchange_data(exchange_id: str):
    """
    Fetch full exchange data (including all tickers) from CoinGecko.
    Returns the JSON dict or None on failure.
    """
    if not exchange_id or not isinstance(exchange_id, str):
        print("❌ Error: Exchange ID cannot be empty.")
        return None

    url = f"https://api.coingecko.com/api/v3/exchanges/{exchange_id.strip().lower()}"
    
    try:
        # Be a good API citizen
        headers = {
            "User-Agent": "Python-Exchange-Fetcher/1.0 (your-email@example.com)"
        }
        
        print(f"🔄 Fetching data for exchange: {exchange_id} ...")
        response = requests.get(url, headers=headers, timeout=15)
        
        # Nice error handling for common cases
        if response.status_code == 404:
            print(f"❌ Exchange ID '{exchange_id}' not found.")
            print("💡 Tip: Check the exact ID on https://www.coingecko.com/en/exchanges")
            return None
        if response.status_code == 429:
            print("⛔ Rate limit hit (free tier ~10–30 calls/min). Wait 60 seconds and try again.")
            return None
        
        response.raise_for_status()
        data = response.json()

        # Pretty summary
        print("\n✅ SUCCESS!")
        print(f"📛 Name           : {data.get('name')}")
        print(f"🔢 Trust Score    : {data.get('trust_score')} / 10 (Rank #{data.get('trust_score_rank') or 'N/A'})")
        print(f"📊 24h Volume BTC : {data.get('trade_volume_24h_btc', 0):,.6f} BTC")
        print(f"🪙 Coins          : {data.get('coins', 0)}")
        print(f"🔄 Pairs          : {data.get('pairs', 0)}")
        print(f"🏛️  Centralized    : {data.get('centralized')}")
        print(f"📅 Year Established: {data.get('year_established') or 'N/A'}")

        tickers = data.get('tickers', [])
        print(f"\n📋 Active Tickers : {len(tickers)} (showing top 8 by volume)")
        for i, t in enumerate(tickers[:8], 1):
            base = t.get('base', 'N/A')
            target = t.get('target', 'N/A')
            last = t.get('last')
            vol_usd = t.get('converted_volume', {}).get('usd', 0)
            traded_at = t.get('last_traded_at')
            if traded_at:
                try:
                    traded_at = datetime.fromisoformat(traded_at.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                except:
                    traded_at = traded_at[:16]
            print(f"   {i:2d}. {base:>8}/{target:<8}  →  ${last:,.8f}   |  24h Vol: ${vol_usd:,.0f}   |  {traded_at}")

        # Optional: save full raw JSON (always useful for later analysis)
        filename = f"{exchange_id}_data.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Full raw data saved → {filename}")

        return data

    except requests.exceptions.RequestException as e:
        print(f"❌ Network/HTTP error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("🚀 Usage: python fetch_exchange_info.py <exchange_id>")
        print("   Example: python fetch_exchange_info.py uniswap-v2-abstract")
        print("            python fetch_exchange_info.py coinbase")
        print("\n💡 Need a list of valid exchange IDs? Visit: https://www.coingecko.com/en/exchanges")
        sys.exit(1)

    exchange_id = sys.argv[1]
    fetch_exchange_data(exchange_id)
