# ==================== CONFIG ====================
NUM_PAGES = 2          # 1 is usually enough for top DEXes; increase only if you want deeper list
PER_PAGE = 250
OUTPUT_FILE = "top_dexes.txt"
LIMIT = 50             # set to None for ALL fetched DEXes
# ===============================================

import requests
from datetime import datetime
import time

def fetch_all_dexes(num_pages: int, per_page: int):
    all_exchanges = []
    
    for page in range(1, num_pages + 1):
        url = "https://api.coingecko.com/api/v3/exchanges"
        params = {"per_page": per_page, "page": page}
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            all_exchanges.extend(data)
            print(f"✅ Fetched page {page} ({len(data)} exchanges)")
            
            if page < num_pages:
                time.sleep(1.5)   # prevent rate-limit
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break
    
    print(f"\nTotal exchanges fetched: {len(all_exchanges)}")
    
    # FIXED: Name-based DEX detection (very reliable for top DEXes)
    dex_keywords = [
        "uniswap", "pancakeswap", "raydium", "orca", "quickswap", "sushiswap",
        "curve", "balancer", "1inch", "dodo", "kyberswap", "trader joe",
        "camelot", "velodrome", "aerodrome", "thena", "apeswap", "biswap",
        "v3", "v2", "(ethereum)", "(bsc)", "(solana)", "(base)", "(arbitrum)"
    ]
    
    dexes = [
        ex for ex in all_exchanges
        if any(kw in ex.get("name", "").lower() for kw in dex_keywords)
    ]
    
    print(f"DEXes found after filtering: {len(dexes)}")
    if dexes:
        print("Sample DEX names:", [d.get("name") for d in dexes[:5]])
    
    # Sort by 24h volume (exactly matches CoinGecko default ranking)
    dexes_sorted = sorted(
        dexes,
        key=lambda x: float(x.get("trade_volume_24h_btc") or 0),
        reverse=True
    )
    
    return dexes_sorted


def save_simple_txt(dexes, filename, limit=None):
    # BTC → USD conversion
    btc_price = None
    try:
        btc_resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10
        )
        btc_price = btc_resp.json()["bitcoin"]["usd"]
        print(f"✅ BTC price fetched: ${btc_price:,.0f}")
    except Exception as e:
        print(f"⚠️ BTC price fetch failed: {e}")

    total_vol_btc = sum(float(d.get("trade_volume_24h_btc") or 0) for d in dexes)
    total_vol_usd = total_vol_btc * btc_price if btc_price else 0

    lines = []
    lines.append("🌐 Top Decentralized Exchanges (CoinGecko ranking by 24h Volume)")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total DEX 24h volume: ~${total_vol_usd:,.0f} USD")
    lines.append("=" * 80)
    lines.append("")

    display_limit = limit if limit is not None else len(dexes)

    for i, dex in enumerate(dexes[:display_limit], 1):
        name = dex.get("name", "Unknown")
        vol_btc = float(dex.get("trade_volume_24h_btc") or 0)
        vol_usd = f"${vol_btc * btc_price:,.0f}" if btc_price else f"{vol_btc:,.2f} BTC"
        market_share = (vol_btc / total_vol_btc * 100) if total_vol_btc > 0 else 0
        
        line = f"{i:2d}. {name:<45} {vol_usd:>18}   {market_share:5.1f}%"
        lines.append(line)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"\n✅ Simple list saved to: {filename} ({display_limit} DEXes written)")


# ==================== RUN ====================
if __name__ == "__main__":
    print("🚀 Fetching top DEXes from CoinGecko...\n")
    
    dexes = fetch_all_dexes(NUM_PAGES, PER_PAGE)
    
    if not dexes:
        print("❌ Still no DEXes found — let me know and we’ll switch to scraping the webpage.")
    else:
        save_simple_txt(dexes, OUTPUT_FILE, LIMIT)
        
        print("\n📋 Top 5 in console:")
        for i, d in enumerate(dexes[:5], 1):
            print(f"{i:2d}. {d.get('name')}")
