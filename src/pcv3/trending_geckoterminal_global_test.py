import requests
import json
from datetime import datetime
import sys

def fetch_global_trending_pools(duration="24h", page=1, per_page=20):
    """
    Fetch GLOBAL trending pools across ALL chains supported by GeckoTerminal.
    
    IMPORTANT: The API is hard-coded to return exactly 20 pools and ignores per_page.
    We now default to 20 to match real behavior.
    
    Chains are mixed together (Solana, Base, Ethereum, TON, Sui, etc.).
    """
    url = "https://api.geckoterminal.com/api/v2/networks/trending_pools"
    
    params = {
        "duration": duration,
        "page": page,
        "per_page": per_page,
        "include": "base_token,quote_token,dex,network"   # added "network" so we get the chain name
    }
    
    headers = {
        "accept": "application/json",
        "User-Agent": "GeckoTerminal-Global-Fixed-Script/2.0"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        pools = data.get("data", [])
        included = data.get("included", [])
        
        print(f"✅ Fetched {len(pools)} GLOBAL trending pools from API (mixed across all chains)")
        return pools, data.get("meta", {}), included
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        if hasattr(e.response, 'text'):
            print("Response:", e.response.text[:500])
        sys.exit(1)


def pretty_print_pool(pool, included):
    """Safe pretty print with correct nested structure + NEW chain display."""
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

    # === 24h metrics (unchanged) ===
    vol_dict = attr.get("volume_usd", {})
    volume_24h = vol_dict.get("h24", "0") if isinstance(vol_dict, dict) else "0"
    
    tx_dict = attr.get("transactions", {}).get("h24", {})
    total_tx_24h = 0
    if isinstance(tx_dict, dict):
        total_tx_24h = int(tx_dict.get("buys", 0)) + int(tx_dict.get("sells", 0))
    else:
        total_tx_24h = int(float(tx_dict or 0))

    change_dict = attr.get("price_change_percentage", {})
    price_change_24h = change_dict.get("h24", "0") if isinstance(change_dict, dict) else "0"

    price = attr.get("base_token_price_usd", attr.get("price_usd", "0"))
    liquidity = attr.get("reserve_in_usd", "0")
    fdv = attr.get("fdv_usd", "0")
    gt_score = attr.get("gt_score", "N/A")

    # === DEX name ===
    try:
        dex_id = rel["dex"]["data"]["id"]
        dex = next((item for item in included if item.get("id") == dex_id), None)
        dex_name = dex["attributes"].get("name", dex_id) if dex else dex_id
    except:
        dex_name = "Unknown DEX"

    # === NEW: Network / Chain name ===
    try:
        network_id = rel["network"]["data"]["id"]
        network = next((item for item in included if item.get("id") == network_id), None)
        network_name = network["attributes"].get("name", network_id) if network else network_id
    except:
        network_name = "Unknown Chain"

    # === PRINT BLOCK ===
    print(f"   Token      : {token_name} ({token_symbol})")
    print(f"   Pool       : {attr.get('name', 'N/A')}")
    print(f"   Chain      : {network_name}")          # ← new line
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
    print("🚀 FIXED GeckoTerminal GLOBAL 24h Trending Pools Fetcher")
    print("   (All chains mixed together — exact match to website)")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # === FETCH ALL 20 GLOBAL POOLS ===
    pools, meta, included = fetch_global_trending_pools(duration="24h", page=1, per_page=20)
    
    # === ENRICH WITH RANK NUMBER FOR JSON ===
    # We create a copy so we never mutate the raw API response
    enriched_pools = []
    for i, pool in enumerate(pools, 1):
        enriched = pool.copy()          # shallow copy is sufficient here
        enriched["rank"] = i
        enriched_pools.append(enriched)
    
    # === CONSOLE: Show ONLY Top 5 (unchanged) ===
    print(f"\n📊 Top 5 GLOBAL trending pools (across ALL chains):\n")
    
    for i, pool in enumerate(pools[:5], 1):
        print(f"#{i} ───────────────────────────────────────")
        pretty_print_pool(pool, included)
        print()  # extra blank line between pools
    
    # === JSON: ALL 20 pools WITH explicit rank ===
    json_filename = "global_trending_24h.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump({
            "pools": enriched_pools,   # ← now contains "rank": 1, 2, ...
            "meta": meta,
            "included": included
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Full data (all 20 global pools WITH RANK) saved to → {json_filename}")


if __name__ == "__main__":
    main()
