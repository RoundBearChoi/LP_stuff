import requests
import time
import json
from typing import List, Dict, Any, Optional

# ========================== CONFIG SECTION ==========================
# ← Everything you can tweak is right here at the top
CONFIG = {
    "networks": ["solana", "bsc", "eth", "base", "arbitrum", "polygon_pos", "hyperliquid"],   # ← UPDATED as requested
    "min_volume_24h_usd": 100_000,                              # ← ONLY filter left: minimum 24h volume (TVL filter removed)
    "max_pages_per_network": 1,                                # safety cap — we usually stop much earlier now
    "output_json": "geckoterminal_top_volume.json",             # JSON export (only format we keep)
    "rate_limit_sleep_seconds": 65,                             # how long to wait on 429
    "max_retries_per_page": 3,                                  # retry the same page up to 3 times on rate limit
    "request_timeout": 15,                                      # seconds
}
# =====================================================================


class GeckoTerminalFetcher:
    """
    Clean OOP wrapper for GeckoTerminal public API.
    
    CHANGES MADE (per your request):
    - target_top_n completely removed
    - Now collects and exports ALL pairs with 24h volume >= min_volume_24h_usd
    - TVL filter already gone; only volume filter remains
    - Smart per-chain early-stop still active (stops the moment volume drops below threshold)
    """

    BASE_URL = "https://api.geckoterminal.com/api/v2"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or CONFIG.copy()
        print("🚀 GeckoTerminalFetcher initialized with config:")
        for k, v in self.config.items():
            print(f"   • {k}: {v}")

    @staticmethod
    def safe_float(value, default: float = 0.0) -> float:
        """Safely convert API strings/numbers to float (handles None, '', 'null', etc.)."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _fetch_page(self, network: str, page: int) -> List[Dict]:
        """Single page fetch with 429 retry logic."""
        url = f"{self.BASE_URL}/networks/{network}/pools"
        params = {
            "page": page,
            "sort": "h24_volume_usd_desc",
            "include": "volume_usd",
        }

        for attempt in range(1, self.config["max_retries_per_page"] + 1):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config["request_timeout"]
                )

                if response.status_code == 429:  # Rate limit
                    sleep_time = self.config["rate_limit_sleep_seconds"]
                    print(f"   ⏳ Rate limit (429) on {network} page {page} — waiting {sleep_time}s (attempt {attempt}/{self.config['max_retries_per_page']})")
                    time.sleep(sleep_time)
                    continue

                response.raise_for_status()
                data = response.json().get("data", [])
                print(f"   ✅ {network} page {page} — {len(data)} pools scanned")
                return data

            except requests.exceptions.RequestException as e:
                if "429" in str(e) or (hasattr(response, "status_code") and response.status_code == 429):
                    sleep_time = self.config["rate_limit_sleep_seconds"]
                    print(f"   ⏳ Rate limit hit on {network} page {page} — waiting {sleep_time}s (attempt {attempt})")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"   ❌ Error on {network} page {page}: {e}")
                    break

        return []  # failed after retries

    def fetch_filtered_top_pairs(self) -> List[Dict[str, Any]]:
        """
        Main method: returns ALL pairs with 24h volume >= min_volume_24h_usd.
        No more target_top_n limit — we export everything that passes the volume filter.
        """
        filtered_pairs: List[Dict[str, Any]] = []

        print("\n" + "=" * 70)
        print("Starting fetch — ONLY 24h volume filter + per-chain early stop")
        print("Collecting ALL qualifying pairs (no artificial top-N limit)")
        print("=" * 70)

        for network in self.config["networks"]:
            print(f"\n🔍 Processing network: {network.upper()}")
            network_stopped_early = False

            for page in range(1, self.config["max_pages_per_network"] + 1):
                pools = self._fetch_page(network, page)

                if not pools:
                    break

                for pool in pools:
                    attrs = pool.get("attributes", {})

                    vol_24h = self.safe_float(attrs.get("volume_usd", {}).get("h24"))

                    # === EARLY-STOP LOGIC ===
                    if vol_24h < self.config["min_volume_24h_usd"]:
                        print(f"   ⚡ Volume dropped below ${self.config['min_volume_24h_usd']:,.0f} "
                              f"on {network} page {page} — stopping this chain early and moving to next network")
                        network_stopped_early = True
                        break

                    # === FILTER: ONLY volume matters now ===
                    if vol_24h >= self.config["min_volume_24h_usd"]:
                        pair_info = {
                            "network": network,
                            "pool_address": pool.get("id"),
                            "name": attrs.get("name", "Unknown Pair"),
                            "tvl_usd": self.safe_float(attrs.get("reserve_in_usd")),   # still collected for info
                            "volume_24h_usd": vol_24h,
                            "fdv_usd": self.safe_float(attrs.get("fdv_usd")),
                            "price_usd": self.safe_float(attrs.get("price_usd")),
                            "base_token_symbol": attrs.get("base_token", {}).get("symbol", ""),
                            "quote_token_symbol": attrs.get("quote_token", {}).get("symbol", ""),
                            "total_tx_24h": (attrs.get("transactions", {}).get("h24", {}).get("buys", 0) +
                                             attrs.get("transactions", {}).get("h24", {}).get("sells", 0)),
                        }
                        filtered_pairs.append(pair_info)

                # If we hit a low-volume pool, we already broke the pool loop — now break the page loop
                if network_stopped_early:
                    break

            # Small politeness delay between networks
            if network != self.config["networks"][-1]:
                time.sleep(2)

        # Final sort by 24h volume (highest first)
        filtered_pairs.sort(key=lambda x: x["volume_24h_usd"], reverse=True)

        # === JSON EXPORT ALL qualifying pairs ===
        if self.config.get("output_json") and filtered_pairs:
            json_path = self.config["output_json"]
            with open(json_path, mode="w", encoding="utf-8") as f:
                json.dump(filtered_pairs, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Exported {len(filtered_pairs)} pairs above volume threshold → {json_path}")

        return filtered_pairs


# ========================== USAGE ==========================
if __name__ == "__main__":
    fetcher = GeckoTerminalFetcher()

    results = fetcher.fetch_filtered_top_pairs()

    print(f"\n🎉 DONE — Found {len(results)} pairs with 24h volume >= ${CONFIG['min_volume_24h_usd']:,.0f}")
    print("-" * 90)

    for i, p in enumerate(results, 1):
        print(f"{i:3d}. {p['name']}  ({p['network'].upper()})")
        print(f"      TVL: ${p['tvl_usd']:,.0f}   |   24h Vol: ${p['volume_24h_usd']:,.0f}")
        print(f"      Pool: {p['pool_address']}")
        print("-" * 90)
