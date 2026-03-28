import requests
import time
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict

# ========================== CONFIG SECTION ==========================
CONFIG = {
    "networks": ["solana", "bsc", "eth", "base", "arbitrum", "polygon_pos", "hyperliquid"],
    "min_volume_24h_usd": 0,                              # pure volume sort
    "max_pages_per_network": 2,                           # change to 5 when you want more results
    "output_prefix": "geckoterminal_top_volume",
    "network_filename_map": {
        "solana": "sol",
        "bsc": "bsc",
        "eth": "eth",
        "base": "base",
        "arbitrum": "arbitrum",
        "polygon_pos": "polygon",
        "hyperliquid": "hyperliquid",
    },
    "rate_limit_sleep_seconds": 65,
    "max_retries_per_page": 3,
    "request_timeout": 15,
}
# =====================================================================


class GeckoTerminalFetcher:
    """
    Clean OOP wrapper for GeckoTerminal public API.

    FIXED VERSION:
    - name field now used directly (already contains perfect "TOKEN / SOL")
    - Added fdv_usd (much more useful than market_cap on Solana)
    - No more empty symbol fields
    - Matches webpage look and feel
    """

    BASE_URL = "https://api.geckoterminal.com/api/v2"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or CONFIG.copy()
        print("🚀 GeckoTerminalFetcher initialized with config:")
        for k, v in self.config.items():
            print(f"   • {k}: {v}")

    @staticmethod
    def safe_float(value, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _fetch_page(self, network: str, page: int) -> List[Dict]:
        url = f"{self.BASE_URL}/networks/{network}/pools"
        print(f"fetching page {page}, h24_volume_usd_desc")

        params = {
            "page": page,
            "sort": "h24_volume_usd_desc",
            "include": "volume_usd,transactions",   # no longer need base/quote tokens
        }

        for attempt in range(1, self.config["max_retries_per_page"] + 1):
            try:
                response = requests.get(url, params=params, timeout=self.config["request_timeout"])

                if response.status_code == 429:
                    sleep_time = self.config["rate_limit_sleep_seconds"]
                    print(f"   ⏳ Rate limit (429) on {network} page {page} — waiting {sleep_time}s")
                    time.sleep(sleep_time)
                    continue

                response.raise_for_status()
                data = response.json().get("data", [])
                print(f"   ✅ {network} page {page} — {len(data)} pools scanned")
                return data

            except requests.exceptions.RequestException as e:
                if "429" in str(e) or (hasattr(response, "status_code") and response.status_code == 429):
                    sleep_time = self.config["rate_limit_sleep_seconds"]
                    print(f"   ⏳ Rate limit hit on {network} page {page} — waiting {sleep_time}s")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"   ❌ Error on {network} page {page}: {e}")
                    break

        return []

    def fetch_filtered_top_pairs(self) -> List[Dict[str, Any]]:
        network_pairs = defaultdict(list)

        print("\n" + "=" * 80)
        print("Starting clean 24h volume fetch (name + FDV + MCAP + Liq + Vol + TXN)")
        print("Exporting clean JSON per chain")
        print("=" * 80)

        for network in self.config["networks"]:
            print(f"\n🔍 Processing network: {network.upper()}")

            for page in range(1, self.config["max_pages_per_network"] + 1):
                pools = self._fetch_page(network, page)
                if not pools:
                    break

                for pool in pools:
                    attrs = pool.get("attributes", {})
                    vol_24h = self.safe_float(attrs.get("volume_usd", {}).get("h24"))

                    if vol_24h >= self.config["min_volume_24h_usd"]:
                        pair_info = {
                            "network": network,
                            "pool_address": pool.get("id"),
                            "name": attrs.get("name", "Unknown Pair"),           # ← this is the good one

                            "fdv_usd": self.safe_float(attrs.get("fdv_usd")),
                            "market_cap_usd": self.safe_float(attrs.get("market_cap_usd")),
                            "tvl_usd": self.safe_float(attrs.get("reserve_in_usd")),   # Liquidity
                            "volume_24h_usd": vol_24h,

                            "total_tx_24h": (attrs.get("transactions", {}).get("h24", {}).get("buys", 0) +
                                             attrs.get("transactions", {}).get("h24", {}).get("sells", 0)),
                        }
                        network_pairs[network].append(pair_info)

            # Export per-chain JSON
            if network_pairs[network]:
                suffix = self.config["network_filename_map"].get(network, network)
                json_path = f"{self.config['output_prefix']}_{suffix}.json"
                network_pairs[network].sort(key=lambda x: x["volume_24h_usd"], reverse=True)
                with open(json_path, mode="w", encoding="utf-8") as f:
                    json.dump(network_pairs[network], f, indent=2, ensure_ascii=False)
                print(f"   💾 Exported {len(network_pairs[network])} pairs for {network.upper()} → {json_path}")
            else:
                print(f"   ⚠️  No pairs for {network.upper()}")

            if network != self.config["networks"][-1]:
                time.sleep(2)

        # Global list + console
        filtered_pairs: List[Dict[str, Any]] = []
        for net in self.config["networks"]:
            filtered_pairs.extend(network_pairs[net])

        filtered_pairs.sort(key=lambda x: x["volume_24h_usd"], reverse=True)

        print(f"\n🎉 DONE — Found {len(filtered_pairs)} pairs (pure 24h volume sort)")
        print("-" * 130)

        # Clean console output
        for i, p in enumerate(filtered_pairs, 1):
            print(f"{i:3d}. {p['name']}  ({p['network'].upper()})")
            print(f"   FDV: ${p['fdv_usd']:,.0f}   |   Market Cap: ${p['market_cap_usd']:,.0f}   |   Liquidity: ${p['tvl_usd']:,.0f}")
            print(f"   24h Vol: ${p['volume_24h_usd']:,.0f}   |   TXN 24h: {p['total_tx_24h']:,}")
            print(f"   Pool: {p['pool_address']}")
            print("-" * 130)

        return filtered_pairs


# ========================== USAGE ==========================
if __name__ == "__main__":
    fetcher = GeckoTerminalFetcher()
    results = fetcher.fetch_filtered_top_pairs()
    print("\n✅ Script finished. JSON files are ready!")
