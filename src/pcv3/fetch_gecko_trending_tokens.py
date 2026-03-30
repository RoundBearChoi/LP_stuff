import requests
import json
from datetime import datetime, timezone   # ← added timezone
import sys
import time  # for polite rate-limit handling
import random  # for jitter on retries

# ========================= CONFIG SECTION =========================
# All user-controllable variables are centralized here.
CONFIG = {
    # API behavior
    "API_URL": "https://api.geckoterminal.com/api/v2/networks/trending_pools",
    "DURATION": "24h",
    "TOTAL_PAGES": 10,
    "PER_PAGE": 20,
    "INCLUDE": "base_token,quote_token,dex,network",

    # Rate-limit handling
    "MAX_RETRIES_ON_429": 5,
    "RETRY_DELAY_SECONDS": 30.0,
    "INTER_PAGE_DELAY": 1.2,

    # HTTP settings
    "USER_AGENT": "GeckoTerminal-Global-Fixed-Script/2.0",
    "TIMEOUT_SECONDS": 15,

    # Filters (set to 0 to disable)
    "MIN_TVL_USD": 1000000,
    "MIN_VOLUME_24H_USD": 100000,
    "MIN_TOKEN_AGE_HOURS": 4320, # ~6 months (180 days)

    # Output settings
    "JSON_FILENAME": "gecko_global_trending_24h.json",
    "TOP_N_TO_PRINT": 5,

    # CoinGecko enrichment
    "COINGECKO_TIMEOUT": 10,
}
# ==================================================================


class GeckoTerminalGlobalFetcher:
    """
    Pure server-side ranking + full token data + CoinGecko links + RANKS + token-age filter.
    """

    def __init__(self, config: dict = None):
        self.config = config or CONFIG.copy()

    # ====================== NEW HELPER ======================
    def _get_pool_age_hours(self, pool: dict) -> float:
        """Calculate pool/token age in hours from pool_created_at (ISO format)."""
        try:
            attr = pool.get("attributes", {})
            created_at_str = attr.get("pool_created_at")
            if not created_at_str:
                return 0.0

            # Normalize "Z" UTC to +00:00 so fromisoformat works
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"

            created_at = datetime.fromisoformat(created_at_str)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600
            return max(0.0, age_hours)   # never return negative
        except Exception as e:
            print(f"   ⚠️  Failed to parse pool_created_at: {e}")
            return 0.0
    # =======================================================

    def fetch_global_trending_pools(self):
        """(unchanged — same as your original)"""
        all_pools = []
        included_map = {}
        total_pages = self.config.get("TOTAL_PAGES", 1)
        max_retries = self.config.get("MAX_RETRIES_ON_429", 5)
        retry_delay = self.config.get("RETRY_DELAY_SECONDS", 30.0)
        inter_page_delay = self.config.get("INTER_PAGE_DELAY", 1.2)
        actual_pages_fetched = 0

        print(f"🚀 Fetching {total_pages} page(s) from GeckoTerminal global trending (pages 1–{total_pages})...")
        print(f"   (Rate-limit retry enabled: up to {max_retries} attempts per page, base delay {retry_delay}s)")
        print(f"   (Inter-page delay: {inter_page_delay}s — this helps avoid 429s)")

        for page_num in range(1, total_pages + 1):
            for attempt in range(max_retries + 1):
                url = self.config["API_URL"]
                params = {
                    "duration": self.config["DURATION"],
                    "page": page_num,
                    "per_page": self.config["PER_PAGE"],
                    "include": self.config["INCLUDE"]
                }
                headers = {"accept": "application/json", "User-Agent": self.config["USER_AGENT"]}

                try:
                    response = requests.get(url, params=params, headers=headers, timeout=self.config["TIMEOUT_SECONDS"])

                    if response.status_code == 429:
                        if attempt == max_retries:
                            print(f"   ❌ Rate limit (429) on page {page_num} — giving up after {max_retries} retries")
                            break
                        wait_time = retry_delay * (2 ** attempt) + random.uniform(0, 3.0)
                        print(f"   ⏳ Rate limit (429) on page {page_num} — waiting {wait_time:.1f}s (retry {attempt+1}/{max_retries})...")
                        time.sleep(wait_time)
                        continue

                    response.raise_for_status()
                    data = response.json()

                    pools = data.get("data", [])
                    included = data.get("included", [])

                    all_pools.extend(pools)
                    actual_pages_fetched += 1

                    for item in included:
                        item_id = item.get("id")
                        if item_id and item_id not in included_map:
                            included_map[item_id] = item

                    print(f"   ✅ Page {page_num}: +{len(pools)} pools")

                    if len(pools) < self.config["PER_PAGE"]:
                        print(f"   📍 Reached last available page at {page_num}")
                        break

                    if page_num < total_pages:
                        time.sleep(inter_page_delay)
                    break

                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed on page {page_num} (attempt {attempt+1}): {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        print(f"   Status code: {e.response.status_code}")
                        if hasattr(e.response, 'text'):
                            print("   Response:", e.response.text[:400])
                    if attempt == max_retries:
                        break
                    time.sleep(2)
                    continue

        combined_included = list(included_map.values())
        print(f"✅ Successfully fetched {len(all_pools)} total pools from {actual_pages_fetched} page(s)")

        return all_pools, {}, combined_included

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

    # ====================== UPDATED FILTER ======================
    def _filter_pools(self, pools: list) -> list:
        min_tvl = float(self.config.get("MIN_TVL_USD", 0))
        min_vol = float(self.config.get("MIN_VOLUME_24H_USD", 0))
        min_age_hours = float(self.config.get("MIN_TOKEN_AGE_HOURS", 0))

        if min_tvl <= 0 and min_vol <= 0 and min_age_hours <= 0:
            return pools[:]

        filtered = []
        age_filtered_out = 0

        for pool in pools:
            tvl = self._get_tvl(pool)
            vol = self._get_volume_24h(pool)
            age_hours = self._get_pool_age_hours(pool)

            if (min_tvl <= 0 or tvl >= min_tvl) and \
               (min_vol <= 0 or vol >= min_vol) and \
               (min_age_hours <= 0 or age_hours >= min_age_hours):
                filtered.append(pool)
            elif min_age_hours > 0 and age_hours < min_age_hours:
                age_filtered_out += 1

        # Nice feedback for the user
        if min_age_hours > 0:
            days = min_age_hours / 24
            print(f"   📅 Age filter applied: kept {len(filtered)} / {len(pools)} pools "
                  f"(filtered out {age_filtered_out} pools younger than {days:.0f} days)")

        return filtered
    # ============================================================

    # (the rest of your original methods — _enrich_pools_with_token_data, _enrich_with_coingecko_ranks, pretty_print_pool — are unchanged)

    def _enrich_pools_with_token_data(self, pools: list, included: list):
        # ... (exactly your original code)
        token_map = {item["id"]: item["attributes"] for item in included if item.get("type") == "token"}

        network_slug_map = {
            "ethereum": "ethereum", "eth": "ethereum", "base": "base", "solana": "solana",
            "bsc": "binance-smart-chain", "bnb": "binance-smart-chain", "arbitrum": "arbitrum",
            "polygon": "polygon-pos", "avalanche": "avalanche", "optimism": "optimistic-ethereum",
            "zksync": "zksync", "blast": "blast", "linea": "linea",
        }

        for pool in pools:
            rel = pool.get("relationships", {})
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
        # ... (exactly your original code — unchanged)
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

        except Exception as e:
            print(f"   ⚠️  CoinGecko rank fetch failed: {e} (ranks will be null)")
            for pool in pools:
                pool["coingecko_rank"] = None

    def pretty_print_pool(self, pool: dict, included: list):
        # (exactly your original code — unchanged)
        attr = pool.get("attributes", {})
        rel = pool.get("relationships", {})

        try:
            base_id = rel["base_token"]["data"]["id"]
            base_token = next((item for item in included if item.get("id") == base_id), None)
            token_name = base_token["attributes"].get("name", "Unknown") if base_token else "Unknown"
            token_symbol = base_token["attributes"].get("symbol", "???") if base_token else "???"
        except:
            token_name = token_symbol = "Unknown"

        contract = pool.get("base_token", {}).get("address") if pool.get("base_token") else "N/A"

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
        print(f"   🔗 CoinGecko: {pool.get('coingecko_link', 'N/A')}")
        rank = pool.get("coingecko_rank")
        print(f"   🏆 CG Rank   : #{rank if rank is not None else 'N/A'} (market-cap based)")

    def run(self):
        print("=" * 80)
        print("🚀 FIXED GeckoTerminal GLOBAL 24h Trending Pools Fetcher")
        print(f"   (Multi-page + 429 retry • TOTAL_PAGES = {self.config.get('TOTAL_PAGES', 1)})")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Age filter: {self.config.get('MIN_TOKEN_AGE_HOURS')} hours minimum")
        print("=" * 80)

        pools, meta, included = self.fetch_global_trending_pools()

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
                "pools": filtered_pools,
                "meta": meta,
                "included": included,
                "filters_applied": {
                    "MIN_TVL_USD": self.config["MIN_TVL_USD"],
                    "MIN_VOLUME_24H_USD": self.config["MIN_VOLUME_24H_USD"],
                    "MIN_TOKEN_AGE_HOURS": self.config["MIN_TOKEN_AGE_HOURS"],   # ← new
                    "pools_fetched": len(pools),
                    "pools_after_filter": len(filtered_pools),
                    "total_pages": self.config.get("TOTAL_PAGES", 1),
                    "retries_used": True
                }
            }, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Enriched data saved to → {json_filename}")


if __name__ == "__main__":
    fetcher = GeckoTerminalGlobalFetcher()
    fetcher.run()
