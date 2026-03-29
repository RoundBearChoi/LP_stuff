import requests
import json
from datetime import datetime
import sys
import time  # for polite rate-limit handling if needed

# ========================= CONFIG SECTION =========================
# All user-controllable variables are centralized here.
CONFIG = {
    # API behavior
    "API_URL": "https://api.geckoterminal.com/api/v2/networks/trending_pools",
    "DURATION": "24h",
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

    # CoinGecko enrichment
    "COINGECKO_TIMEOUT": 10,
}
# ==================================================================


class GeckoTerminalGlobalFetcher:
    """
    Pure server-side ranking + full token data + CoinGecko links + CoinGecko ranks.
    Field "rank" renamed to "gecko_terminal_rank" for clarity.
    """

    def __init__(self, config: dict = None):
        self.config = config or CONFIG.copy()

    def fetch_global_trending_pools(self):
        url = self.config["API_URL"]
        params = {
            "duration": self.config["DURATION"],
            "page": self.config["PAGE"],
            "per_page": self.config["PER_PAGE"],
            "include": self.config["INCLUDE"]
        }
        headers = {"accept": "application/json", "User-Agent": self.config["USER_AGENT"]}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=self.config["TIMEOUT_SECONDS"])
            response.raise_for_status()
            data = response.json()
            pools = data.get("data", [])
            included = data.get("included", [])
            print(f"✅ Fetched {len(pools)} GLOBAL trending pools from API")
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

    def _enrich_pools_with_token_data(self, pools: list, included: list):
        """Embed base/quote token data + direct CoinGecko link."""
        token_map = {item["id"]: item["attributes"] for item in included if item.get("type") == "token"}

        network_slug_map = {
            "ethereum": "ethereum", "eth": "ethereum", "base": "base", "solana": "solana",
            "bsc": "binance-smart-chain", "bnb": "binance-smart-chain", "arbitrum": "arbitrum",
            "polygon": "polygon-pos", "avalanche": "avalanche", "optimism": "optimistic-ethereum",
            "zksync": "zksync", "blast": "blast", "linea": "linea",
        }

        for pool in pools:
            rel = pool.get("relationships", {})
            # Base token
            try:
                base_id = rel["base_token"]["data"]["id"]
                base_attrs = token_map.get(base_id, {})
                pool["base_token"] = {
                    "name": base_attrs.get("name"),
                    "symbol": base_attrs.get("symbol"),
                    "address": base_attrs.get("address"),
                    "coingecko_coin_id": base_attrs.get("coingecko_coin_id")
                }
            except:
                pool["base_token"] = None

            # Quote token
            try:
                quote_id = rel["quote_token"]["data"]["id"]
                quote_attrs = token_map.get(quote_id, {})
                pool["quote_token"] = {
                    "name": quote_attrs.get("name"),
                    "symbol": quote_attrs.get("symbol"),
                    "address": quote_attrs.get("address"),
                    "coingecko_coin_id": quote_attrs.get("coingecko_coin_id")
                }
            except:
                pool["quote_token"] = None

            # CoinGecko link
            base = pool.get("base_token")
            if base and base.get("coingecko_coin_id"):
                pool["coingecko_link"] = f"https://www.coingecko.com/en/coins/{base['coingecko_coin_id']}"
            elif base and base.get("address"):
                network_id = rel.get("network", {}).get("data", {}).get("id")
                network_name = next(
                    (item["attributes"].get("name", network_id) for item in included
                     if item.get("id") == network_id), network_id
                ).lower()
                slug = network_slug_map.get(network_name, network_name)
                pool["coingecko_link"] = f"https://www.coingecko.com/en/coins/{slug}/contract/{base['address']}"
            else:
                pool["coingecko_link"] = None

    def _enrich_with_coingecko_ranks(self, pools: list):
        """Batch fetch CoinGecko market_cap_rank for all tokens that have a coingecko_coin_id."""
        coin_ids = {
            pool["base_token"]["coingecko_coin_id"]
            for pool in pools
            if pool.get("base_token") and pool["base_token"].get("coingecko_coin_id")
        }
        if not coin_ids:
            print("   ℹ️  No CoinGecko coin IDs found — skipping rank enrichment")
            return

        print(f"   🔄 Fetching CoinGecko ranks for {len(coin_ids)} unique tokens...")

        ids_param = ",".join(coin_ids)
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": ids_param,
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }

        try:
            response = requests.get(url, params=params, timeout=self.config["COINGECKO_TIMEOUT"])
            response.raise_for_status()
            data = response.json()
            rank_map = {coin["id"]: coin.get("market_cap_rank") for coin in data if isinstance(coin, dict)}

            for pool in pools:
                base = pool.get("base_token")
                if base and base.get("coingecko_coin_id"):
                    pool["coingecko_rank"] = rank_map.get(base["coingecko_coin_id"])
                else:
                    pool["coingecko_rank"] = None

            print(f"   ✅ CoinGecko ranks enriched ({len(rank_map)} coins)")

        except requests.exceptions.RequestException as e:
            print(f"   ⚠️  CoinGecko rank fetch failed: {e} (ranks will be null)")
            for pool in pools:
                pool["coingecko_rank"] = None
        except Exception as e:
            print(f"   ⚠️  Unexpected error during rank enrichment: {e}")
            for pool in pools:
                pool["coingecko_rank"] = None

    def pretty_print_pool(self, pool: dict, included: list):
        """Pretty print with contract, CoinGecko link, and CG Rank."""
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

        contract = pool.get("base_token", {}).get("address") if pool.get("base_token") else "N/A"

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
        print(f"   Contract   : {contract}  ({network_name})")
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
        print(f"   🔗 CoinGecko: {pool.get('coingecko_link', 'N/A')}")
        rank = pool.get("coingecko_rank")
        print(f"   🏆 CG Rank   : #{rank if rank is not None else 'N/A'} (market-cap based)")

    def run(self):
        print("=" * 80)
        print("🚀 FIXED GeckoTerminal GLOBAL 24h Trending Pools Fetcher")
        print("   (Server-side ranking + token addresses + CoinGecko links + RANKS)")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        pools, meta, included = self.fetch_global_trending_pools()

        # === ASSIGN GECKO TERMINAL RANK (explicit key) ===
        for i, pool in enumerate(pools, 1):
            pool["gecko_terminal_rank"] = i

        filtered_pools = self._filter_pools(pools)
        print(f"✅ {len(filtered_pools)} pools passed your filters")

        self._enrich_pools_with_token_data(filtered_pools, included)
        self._enrich_with_coingecko_ranks(filtered_pools)

        top_n = self.config["TOP_N_TO_PRINT"]
        print(f"\n📊 Top {top_n} GLOBAL trending pools (GeckoTerminal server-side ranking):\n")

        for pool in filtered_pools[:top_n]:
            print(f"#{pool['gecko_terminal_rank']} (GeckoTerminal rank) ───────────────────────────────────────")
            self.pretty_print_pool(pool, included)
            print()

        json_filename = self.config["JSON_FILENAME"]
        with open(json_filename, "w", encoding="utf-8") as f:
            json.dump({
                "pools": filtered_pools,   # now contains gecko_terminal_rank + coingecko_rank
                "meta": meta,
                "included": included,
                "filters_applied": {
                    "MIN_TVL_USD": self.config["MIN_TVL_USD"],
                    "MIN_VOLUME_24H_USD": self.config["MIN_VOLUME_24H_USD"],
                    "pools_fetched": len(pools),
                    "pools_after_filter": len(filtered_pools)
                }
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Enriched data saved to → {json_filename}")


if __name__ == "__main__":
    fetcher = GeckoTerminalGlobalFetcher()
    fetcher.run()
