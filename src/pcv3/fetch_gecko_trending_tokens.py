import requests
import json
from datetime import datetime
import sys

# ========================= CONFIG SECTION =========================
# All user-controllable variables are centralized here.
# Change any value below — no need to touch the class code.
CONFIG = {
    # API behavior
    "API_URL": "https://api.geckoterminal.com/api/v2/networks/trending_pools",
    "DURATION": "24h",                  # "24h", "1h", "6h", etc.
    "PAGE": 1,
    "PER_PAGE": 20,
    "INCLUDE": "base_token,quote_token,dex,network",

    # HTTP settings
    "USER_AGENT": "GeckoTerminal-Global-Fixed-Script/2.0",
    "TIMEOUT_SECONDS": 15,

    # Filters (set to 0 to disable)
    "MIN_TVL_USD": 1000000,
    "MIN_VOLUME_24H_USD": 100000,

    # Output settings
    "JSON_FILENAME": "gecko_global_trending_24h.json",
    "TOP_N_TO_PRINT": 5,
}
# ==================================================================


class GeckoTerminalGlobalFetcher:
    """
    PURE server-side ranking only.
    No client-side re-numbering whatsoever.
    Filters are applied but original Gecko rank is preserved.
    """

    def __init__(self, config: dict = None):
        self.config = config or CONFIG.copy()

    def fetch_global_trending_pools(self):
        """Fetch GLOBAL trending pools — already ranked server-side by Gecko."""
        url = self.config["API_URL"]

        params = {
            "duration": self.config["DURATION"],
            "page": self.config["PAGE"],
            "per_page": self.config["PER_PAGE"],
            "include": self.config["INCLUDE"]
        }

        headers = {
            "accept": "application/json",
            "User-Agent": self.config["USER_AGENT"]
        }

        try:
            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=self.config["TIMEOUT_SECONDS"]
            )
            response.raise_for_status()

            data = response.json()
            pools = data.get("data", [])
            included = data.get("included", [])

            print(f"✅ Fetched {len(pools)} GLOBAL trending pools from API (already ranked server-side by Gecko)")
            return pools, data.get("meta", {}), included

        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}")
            if hasattr(e.response, 'text'):
                print("Response:", e.response.text[:500])
            sys.exit(1)

    def _get_tvl(self, pool: dict) -> float:
        try:
            return float(pool.get("attributes", {}).get("reserve_in_usd", 0))
        except (ValueError, TypeError):
            return 0.0

    def _get_volume_24h(self, pool: dict) -> float:
        attr = pool.get("attributes", {})
        vol_dict = attr.get("volume_usd", {})
        try:
            if isinstance(vol_dict, dict):
                return float(vol_dict.get("h24", 0))
            return float(vol_dict or 0)
        except (ValueError, TypeError):
            return 0.0

    def _filter_pools(self, pools: list) -> list:
        """Apply filters while preserving original server-side order."""
        min_tvl = float(self.config.get("MIN_TVL_USD", 0))
        min_vol = float(self.config.get("MIN_VOLUME_24H_USD", 0))

        if min_tvl <= 0 and min_vol <= 0:
            return pools[:]

        filtered = []
        for pool in pools:
            tvl = self._get_tvl(pool)
            vol = self._get_volume_24h(pool)
            if (min_tvl <= 0 or tvl >= min_tvl) and (min_vol <= 0 or vol >= min_vol):
                filtered.append(pool)
        return filtered

    def pretty_print_pool(self, pool: dict, included: list):
        """Pretty print (unchanged)."""
        attr = pool.get("attributes", {})
        rel = pool.get("relationships", {})

        # Token name
        try:
            base_id = rel["base_token"]["data"]["id"]
            base_token = next((item for item in included if item.get("id") == base_id), None)
            token_name = base_token["attributes"].get("name", "Unknown") if base_token else "Unknown"
            token_symbol = base_token["attributes"].get("symbol", "???") if base_token else "???"
        except:
            token_name = token_symbol = "Unknown"

        # 24h metrics
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

        # DEX & Chain
        try:
            dex_id = rel["dex"]["data"]["id"]
            dex = next((item for item in included if item.get("id") == dex_id), None)
            dex_name = dex["attributes"].get("name", dex_id) if dex else dex_id
        except:
            dex_name = "Unknown DEX"

        try:
            network_id = rel["network"]["data"]["id"]
            network = next((item for item in included if item.get("id") == network_id), None)
            network_name = network["attributes"].get("name", network_id) if network else network_id
        except:
            network_name = "Unknown Chain"

        print(f"   Token      : {token_name} ({token_symbol})")
        print(f"   Pool       : {attr.get('name', 'N/A')}")
        print(f"   Chain      : {network_name}")
        print(f"   DEX        : {dex_name}")
        print(f"   24h Volume : ${float(volume_24h):,}")
        print(f"   24h Txns   : {total_tx_24h:,}")
        print(f"   Price      : ${float(price):.8f}")
        print(f"   24h Change : {float(price_change_24h):+.2f}%")
        print(f"   Liquidity  : ${float(liquidity):,}")
        print(f"   FDV        : ${float(fdv):,}")
        print(f"   GT Score   : {gt_score}/100")

    def run(self):
        """Main flow — 100% server-side ranking, no client-side renumbering."""
        print("=" * 80)
        print("🚀 FIXED GeckoTerminal GLOBAL 24h Trending Pools Fetcher")
        print("   (Pure server-side ranking from GeckoTerminal)")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # === FETCH (already in server-side ranked order) ===
        pools, meta, included = self.fetch_global_trending_pools()

        # === ASSIGN SERVER-SIDE RANK (once, before any filtering) ===
        for i, pool in enumerate(pools, 1):
            pool["rank"] = i   # ← pure Gecko server rank

        # === APPLY FILTERS (preserves order) ===
        filtered_pools = self._filter_pools(pools)
        print(f"✅ {len(filtered_pools)} pools passed your filters "
              f"(MIN_TVL_USD=${self.config['MIN_TVL_USD']:,} | "
              f"MIN_VOLUME_24H_USD=${self.config['MIN_VOLUME_24H_USD']:,})")

        if not filtered_pools:
            print("⚠️  No pools met your minimum thresholds.")
            filtered_pools = []

        # === CONSOLE: Show using ORIGINAL Gecko rank ===
        top_n = self.config["TOP_N_TO_PRINT"]
        print(f"\n📊 Top {top_n} GLOBAL trending pools that passed filters "
              f"(showing **original Gecko server-side ranking**):\n")

        for pool in filtered_pools[:top_n]:
            print(f"#{pool['rank']} ───────────────────────────────────────")  # ← server rank
            self.pretty_print_pool(pool, included)
            print()

        # === JSON: Filtered pools with original Gecko rank ===
        json_filename = self.config["JSON_FILENAME"]
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump({
                "pools": filtered_pools,   # already contain "rank" = Gecko server rank
                "meta": meta,
                "included": included,
                "filters_applied": {
                    "MIN_TVL_USD": self.config["MIN_TVL_USD"],
                    "MIN_VOLUME_24H_USD": self.config["MIN_VOLUME_24H_USD"],
                    "pools_fetched": len(pools),
                    "pools_after_filter": len(filtered_pools)
                }
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Filtered data ({len(filtered_pools)} pools with original Gecko ranks) saved to → {json_filename}")


if __name__ == "__main__":
    fetcher = GeckoTerminalGlobalFetcher()
    fetcher.run()
