import requests
import time
import json
from typing import List, Dict, Any, Optional
from collections import defaultdict

# ========================== CONFIG SECTION ==========================
CONFIG = {
    "networks": ["solana",
                 '''
                 "bsc", "eth", "base", "arbitrum", "polygon_pos", "hyperliquid"
                 '''
                 ],
    "min_volume_24h_usd": 0,                              # ← ONLY filter left
    "max_pages_per_network": 2,                                # safety cap
    "output_prefix": "geckoterminal_top_volume",               # ← base name for per-chain files
    "network_filename_map": {                                  # ← maps API network → your desired filename suffix
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

    UPDATES:
    - Separate JSON file per chain
    - unique_buyers_24h, unique_sellers_24h, unique_traders_24h_approx
    - base_token_symbol + quote_token_symbol parsed directly from the 'name' field (reliable, zero extra API cost)
    - Trader-profile flags (whale_heavy / bot_like / volume_per_trader_usd) completely removed per your request
    - Still returns a single flat list for backward compatibility
    - Only 24h volume filter remains
    """

    BASE_URL = "https://api.geckoterminal.com/api/v2"

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or CONFIG.copy()
        print("🚀 GeckoTerminalFetcher initialized with config:")
        for k, v in self.config.items():
            print(f"   • {k}: {v}")

    @staticmethod
    def safe_float(value, default: float = 0.0) -> float:
        """Safely convert API strings/numbers to float."""
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _parse_pair_name(name: str) -> tuple[str, str]:
        """
        Reliably extract base_token_symbol and quote_token_symbol from the pool 'name' field.
        GeckoTerminal always returns names in the format "BASE / QUOTE" (or "BASE/QUOTE").
        This parser is:
          - Fast (string split, no API calls)
          - Robust (handles spaces, "U.S. VDOR" style names, missing slash fallback)
          - Consistent with every pool in the current top-volume data
        """
        if not name or "/" not in name:
            return "", ""
        # Split on the FIRST '/' only (in case a token name itself contains '/')
        parts = [p.strip() for p in name.split("/", 1)]
        return parts[0], parts[1] if len(parts) > 1 else ""

    def _fetch_page(self, network: str, page: int) -> List[Dict]:
        """Single page fetch with 429 retry logic."""
        url = f"{self.BASE_URL}/networks/{network}/pools"
        print(f"fetching page {page}, h24_volume_usd_desc")
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

                if response.status_code == 429:
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

        return []

    def fetch_filtered_top_pairs(self) -> List[Dict[str, Any]]:
        """
        Main method: returns ALL pairs (flat list) with 24h volume >= min_volume_24h_usd.
        Also exports one JSON file per chain (now includes parsed base/quote symbols).
        """
        network_pairs = defaultdict(list)

        print("\n" + "=" * 70)
        print("Starting fetch — ONLY 24h volume filter + per-chain early stop")
        print("Exporting separate JSON per chain (with parsed base/quote symbols)")
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
                              f"on {network} page {page} — stopping this chain early")
                        network_stopped_early = True
                        break

                    # === FILTER & COLLECT ===
                    if vol_24h >= self.config["min_volume_24h_usd"]:
                        tx = attrs.get("transactions", {}).get("h24", {})
                        traders_approx = (self.safe_float(tx.get("buyers")) +
                                          self.safe_float(tx.get("sellers")))

                        # === Parse symbols from name field ===
                        base_symbol, quote_symbol = self._parse_pair_name(attrs.get("name", ""))

                        pair_info = {
                            "network": network,
                            "pool_address": pool.get("id"),
                            "name": attrs.get("name", "Unknown Pair"),
                            "tvl_usd": self.safe_float(attrs.get("reserve_in_usd")),
                            "volume_24h_usd": vol_24h,
                            "fdv_usd": self.safe_float(attrs.get("fdv_usd")),
                            "price_usd": self.safe_float(attrs.get("price_usd")),
                            "base_token_symbol": base_symbol,      # ← now populated
                            "quote_token_symbol": quote_symbol,    # ← now populated
                            "total_tx_24h": (tx.get("buys", 0) + tx.get("sells", 0)),

                            # Trader fields (kept because they are useful)
                            "unique_buyers_24h": self.safe_float(tx.get("buyers")),
                            "unique_sellers_24h": self.safe_float(tx.get("sellers")),
                            "unique_traders_24h_approx": traders_approx,
                        }
                        network_pairs[network].append(pair_info)

                if network_stopped_early:
                    break

            # === EXPORT PER-CHAIN JSON ===
            if network_pairs[network]:
                suffix = self.config["network_filename_map"].get(network, network)
                json_path = f"{self.config['output_prefix']}_{suffix}.json"

                network_pairs[network].sort(key=lambda x: x["volume_24h_usd"], reverse=True)
                with open(json_path, mode="w", encoding="utf-8") as f:
                    json.dump(network_pairs[network], f, indent=2, ensure_ascii=False)
                print(f"   💾 Exported {len(network_pairs[network])} pairs for {network.upper()} → {json_path}")
            else:
                print(f"   ⚠️  No pairs above volume threshold for {network.upper()}")

            # Politeness delay between networks
            if network != self.config["networks"][-1]:
                time.sleep(2)

        # === GLOBAL LIST FOR RETURN + CONSOLE ===
        filtered_pairs: List[Dict[str, Any]] = []
        for net in self.config["networks"]:
            filtered_pairs.extend(network_pairs[net])

        filtered_pairs.sort(key=lambda x: x["volume_24h_usd"], reverse=True)

        print(f"\n🎉 DONE — Found {len(filtered_pairs)} pairs with 24h volume >= ${CONFIG['min_volume_24h_usd']:,.0f}")
        print("-" * 110)

        for i, p in enumerate(filtered_pairs, 1):
            print(f"{i:3d}. {p['name']}  ({p['network'].upper()})")
            print(f"      TVL: ${p['tvl_usd']:,.0f}   |   24h Vol: ${p['volume_24h_usd']:,.0f}")
            print(f"      Base: {p['base_token_symbol']}   |   Quote: {p['quote_token_symbol']}")
            print(f"      Unique Buyers: {int(p['unique_buyers_24h']):,} | Unique Sellers: {int(p['unique_sellers_24h']):,} | Approx Traders: {int(p['unique_traders_24h_approx']):,}")
            print(f"      Pool: {p['pool_address']}")
            print("-" * 110)

        return filtered_pairs


# ========================== USAGE ==========================
if __name__ == "__main__":
    fetcher = GeckoTerminalFetcher()
    results = fetcher.fetch_filtered_top_pairs()
