import requests
import json
from datetime import datetime
import sys

def fetch_solana_trending_pools(duration="24h", page=1, per_page=20):
    """
    Fetch Solana pools sorted by 24h trending score (exact match to website).
    Note: trending_pools endpoint caps at ~20 per page.
    """
    url = "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools"
    
    params = {
        "duration": duration,
        "page": page,
        "per_page": per_page,
        "include": "base_token,quote_token,dex"   # needed for token names + DEX
    }
    
    headers = {
        "accept": "application/json",
        "User-Agent": "GeckoTerminal-Fixed-Script/2.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        pools = data.get("data", [])
        included = data.get("included", [])
        
        print(f"✅ Fetched {len(pools)} trending pools (page {page}, duration={duration})")
        return pools, data.get("meta", {}), included
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e.response, 'text'):
            print("Response:", e.response.text[:500])
        sys.exit(1)


def pretty_print_pool(pool, included):
    """Safe pretty print with correct nested structure from current API."""
    attr = pool.get("attributes", {})
    rel = pool.get("relationships", {})
    
    # === Token name (from included) ===
    try:
        base_id = rel["base_token"]["data"]["id"]
        base_token = next((item for item in included if item.get("id") == base_id), None)
        token_name = base_token["attributes"].get("name", "Unknown") if base_token else "Unknown"
        token_symbol = base_token["attributes"].get("symbol", "???") if base_token else "???"
    except:
        token_name = token_symbol = "Unknown"

    # === 24h metrics (now nested) ===
    # Volume
    vol_dict = attr.get("volume_usd", {})
    volume_24h = vol_dict.get("h24", "0") if isinstance(vol_dict, dict) else "0"
    
    # Transactions (h24 is usually a dict with buys/sells)
    tx_dict = attr.get("transactions", {}).get("h24", {})
    total_tx_24h = 0
    if isinstance(tx_dict, dict):
        total_tx_24h = int(tx_dict.get("buys", 0)) + int(tx_dict.get("sells", 0))
    else:
        total_tx_24h = int(float(tx_dict or 0))

    # Price change
    change_dict = attr.get("price_change_percentage", {})
    price_change_24h = change_dict.get("h24", "0") if isinstance(change_dict, dict) else "0"

    # Other direct fields
    price = attr.get("base_token_price_usd", attr.get("price_usd", "0"))
    liquidity = attr.get("reserve_in_usd", "0")
    fdv = attr.get("fdv_usd", "0")
    gt_score = attr.get("gt_score", "N/A")

    # DEX name
    try:
        dex_id = rel["dex"]["data"]["id"]
        dex = next((item for item in included if item.get("id") == dex_id), None)
        dex_name = dex["attributes"].get("name", dex_id) if dex else dex_id
    except:
        dex_name = "Unknown DEX"

    print(f"\n🔥 #{pool.get('id', 'N/A')[:12]}...")   # shortened pool ID for cleanliness
    print(f"   Token      : {token_name} ({token_symbol})")
    print(f"   Pool       : {attr.get('name', 'N/A')}")
    print(f"   DEX        : {dex_name}")
    print(f"   24h Volume : ${float(volume_24h):,}")
    print(f"   24h Txns   : {total_tx_24h:,}")
    print(f"   Price      : ${float(price):.8f}")
    print(f"   24h Change : {float(price_change_24h):+.2f}%")
    print(f"   Liquidity  : ${float(liquidity):,}")
    print(f"   FDV        : ${float(fdv):,}")
    print(f"   GT Score   : {gt_score}/100")


def main():
    print("=" * 80)
    print("🚀 FIXED GeckoTerminal Solana 24h Trending Pools Fetcher")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    pools, meta, included = fetch_solana_trending_pools(duration="24h", page=1, per_page=20)
    
    print(f"\n📊 Top {len(pools)} Solana pools ranked by 24h trend score:\n")
    
    for i, pool in enumerate(pools, 1):
        pretty_print_pool(pool, included)
    
    # Optional: full JSON export
    with open(f"solana_trending_24h_{datetime.now().strftime('%Y%m%d_%H%M')}.json", "w", encoding="utf-8") as f:
        json.dump({"pools": pools, "meta": meta, "included": included}, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full data saved to JSON.")
    print(f"🔗 Matches exactly: https://www.geckoterminal.com/solana/pools?sort=-24h_trend_score")


if __name__ == "__main__":
    main()
