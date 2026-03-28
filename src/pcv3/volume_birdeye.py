import requests
import sys
import time
from typing import List, Dict, Any

# ========================= CONFIG (TEST MODE) =========================
MIN_TVL = 1_000_000
MIN_24H_VOLUME = 100_000
TOP_N = 100                     # Smaller for quick testing (change to 300 later)

TOKENS_PER_CHAIN = 20           # ← LOWERED for fast testing (max is 100)
DELAY_BETWEEN_CHAINS = 2.5      # Keeps free-tier 100% safe

# Only chains that reliably work with /defi/v3/token/list
WORKING_V3_CHAINS = [
    "solana", "ethereum", "bsc", "base", "monad",
    "hyperevm", "fogo", "mantle", "megaeth"
]
# =====================================================================

BASE_URL = "https://public-api.birdeye.so"


def get_supported_chains(api_key: str) -> List[str]:
    url = f"{BASE_URL}/defi/networks"
    headers = {"accept": "application/json", "X-API-KEY": api_key}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    chains = response.json().get("data", [])
    print(f"✅ Found {len(chains)} supported chains")
    return chains


def fetch_top_tokens_for_chain(chain: str, api_key: str) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/defi/v3/token/list"
    params = {
        "sort_by": "volume_24h_usd",
        "sort_type": "desc",
        "min_liquidity": MIN_TVL,
        "min_volume_24h_usd": MIN_24H_VOLUME,
        "offset": 0,
        "limit": TOKENS_PER_CHAIN,
    }
    headers = {
        "accept": "application/json",
        "X-API-KEY": api_key,
        "x-chain": chain,
    }

    response = requests.get(url, params=params, headers=headers, timeout=15)

    if response.status_code == 429:
        print(f"⚠️  Rate limited on {chain} (free tier)")
        return []
    if response.status_code == 400:
        print(f"⚠️  V3 token list not supported on {chain} yet (Birdeye limitation)")
        return []
    if response.status_code >= 400:
        print(f"⚠️  Error {response.status_code} on {chain}: {response.text[:150]}")
        return []

    data = response.json()
    items = data.get("data", {}).get("items", [])
    print(f"   • {chain}: {len(items)} tokens met filters")
    return items


def main():
    print("🚀 Birdeye Highest Volume Tokens (FREE TIER - TEST MODE)")
    print("   → TOKENS_PER_CHAIN=20 | Only 1 page per chain | Super safe\n")
    print("=" * 75)

    api_key = input("\nEnter your Birdeye free-tier API key: ").strip()
    if not api_key:
        print("❌ API key cannot be empty!")
        sys.exit(1)

    print("\n🔍 Starting quick test fetch...\n")

    all_chains = get_supported_chains(api_key)
    chains = [c for c in all_chains if c in WORKING_V3_CHAINS]

    print(f"📌 Querying {len(chains)} V3-supported chains: {chains}\n")

    all_tokens = []

    for i, chain in enumerate(chains, 1):
        print(f"📡 [{i:2d}/{len(chains)}] Querying {chain}...")
        try:
            tokens = fetch_top_tokens_for_chain(chain, api_key)
            for t in tokens:
                t["chain"] = chain
            all_tokens.extend(tokens)
        except Exception as e:
            print(f"   ❌ Unexpected error on {chain}: {e}")
        finally:
            time.sleep(DELAY_BETWEEN_CHAINS)

    if not all_tokens:
        print("❌ No tokens found.")
        return

    all_tokens.sort(key=lambda x: x.get("volume_24h_usd", 0), reverse=True)
    top_n = all_tokens[:TOP_N]

    print("\n" + "="*130)
    print(f"🏆 TOP {TOP_N} HIGHEST VOLUME TOKENS (TEST RUN)")
    print("="*130)

    for i, token in enumerate(top_n, 1):
        vol = token.get("volume_24h_usd", 0)
        tvl = token.get("liquidity", 0)
        print(f"{i:2d}. [{token['chain'].upper():9}] {token['symbol']:<12} "
              f"│ Vol: ${vol:,.0f} │ TVL: ${tvl:,.0f} │ {token['name']}")
        print(f"    Address: {token['address']}")
        print(f"    MC: ${token.get('market_cap', 0):,.0f}  │  FDV: ${token.get('fdv', 0):,.0f}\n")

    import json
    with open("birdeye_top_volume_tokens_TEST.json", "w") as f:
        json.dump(top_n, f, indent=2)
    print(f"💾 Saved top {TOP_N} to birdeye_top_volume_tokens_TEST.json")
    print("✅ Test complete! Ready to increase TOKENS_PER_CHAIN if you want more data.")


if __name__ == "__main__":
    main()
