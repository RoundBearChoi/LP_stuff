import requests
import json
import os
from datetime import datetime

# ========================= CONFIG =========================
SYMBOLS_CACHE_FILE = "mexc_symbols.json"
OUTPUT_FILE = "mexc_top_volume.json"   # ← Exactly as requested
TOP_N = 200
# ======================================================

def load_or_fetch_symbols():
    """Load symbols metadata from cache if it exists, otherwise fetch once and cache."""
    if os.path.exists(SYMBOLS_CACHE_FILE):
        print(f"✅ Loading cached symbols from {SYMBOLS_CACHE_FILE}")
        with open(SYMBOLS_CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Create fast lookup: symbol → full info
        return {s['symbol']: s for s in data.get('symbols', [])}
    
    print("📡 Fetching fresh symbols metadata from MEXC (this happens ONLY the first time)...")
    response = requests.get("https://api.mexc.com/api/v3/exchangeInfo")
    response.raise_for_status()
    data = response.json()
    
    with open(SYMBOLS_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"✅ Saved {len(data.get('symbols', [])):,} trading pairs to {SYMBOLS_CACHE_FILE}")
    return {s['symbol']: s for s in data.get('symbols', [])}

def fetch_24hr_ticker():
    """Fetch current 24hr ticker statistics (always fresh)."""
    print("📡 Fetching live 24hr ticker data from MEXC...")
    response = requests.get("https://api.mexc.com/api/v3/ticker/24hr")
    response.raise_for_status()
    return response.json()

def get_quote_volume_usd(ticker, quote_asset):
    """Convert quoteVolume to approximate USD volume.
    Exact for stablecoin quotes; raw for fiat (BRL/EUR/etc.)."""
    quote_vol = float(ticker.get('quoteVolume', 0))
    if quote_asset in {'USDT', 'USDC', 'USDE', 'USD1'}:
        return round(quote_vol, 2)
    else:
        # For non-stable quotes (BRL, EUR, etc.) we keep the raw value.
        return round(quote_vol, 2)

# ======================= MAIN =======================
print("🚀 MEXC Top Volume Fetch + Enhancement Script\n")

# 1. Symbols (cached)
symbols_dict = load_or_fetch_symbols()

# 2. Fresh ticker data
tickers = fetch_24hr_ticker()

# 3. Enrich every ticker with base/quote + USD volume
enhanced_list = []
for ticker in tickers:
    symbol = ticker.get('symbol')
    if symbol in symbols_dict:
        info = symbols_dict[symbol]
        base_asset = info['baseAsset']
        quote_asset = info['quoteAsset']
        
        entry = {
            "rank": 0,  # will be set after sorting
            "symbol": symbol,
            "base_asset": base_asset,
            "quote_asset": quote_asset,
            "quote_volume_usd": get_quote_volume_usd(ticker, quote_asset),
            "base_volume": float(ticker.get('volume', 0)),
            "price_change_percent": float(ticker.get('priceChangePercent', 0)),
            "last_price": float(ticker.get('lastPrice', 0)),
            "high_price": float(ticker.get('highPrice', 0)),
            "low_price": float(ticker.get('lowPrice', 0))
        }
        enhanced_list.append(entry)

# 4. Sort by USD volume descending + add ranks
enhanced_list.sort(key=lambda x: x["quote_volume_usd"], reverse=True)

for rank, item in enumerate(enhanced_list[:TOP_N], start=1):
    item["rank"] = rank

top_volume = enhanced_list[:TOP_N]

# 5. Save the final enhanced file
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(top_volume, f, indent=2)

# ======================= SUMMARY =======================
print(f"\n✅ DONE! Top {TOP_N} volume pairs saved to '{OUTPUT_FILE}'")
print(f"   • Total pairs processed: {len(enhanced_list):,}")
print(f"   • Top pair: {top_volume[0]['symbol']} → ${top_volume[0]['quote_volume_usd']:,.2f} USD volume")
print(f"   • Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}")
print(f"   • Symbols cache used: {'✅ Yes' if os.path.exists(SYMBOLS_CACHE_FILE) else '❌ No (just created)'}")
