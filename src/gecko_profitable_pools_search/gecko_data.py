import requests
import pandas as pd
import time
import random

class GeckoPoolScanner:
    """
    GeckoTerminal pool scanner with rate-limit awareness.
    Scans specified DEXes for pools with high liquidity and high daily transaction count.
    """

    def __init__(
        self,
        min_liquidity_usd=1_000_000,
        min_daily_tx=10_000,
        max_pages_per_dex=10,               # increased a bit since you're willing to wait
        sort_by='daily_tx',
        sort_ascending=False,
        output_csv='geckoterminal_high_activity_pools.csv',
        calls_per_min_cap=20,               # conservative to avoid 429
        sleep_between_pages=7.0,            # safer delay
        sleep_between_dexes=15.0,
        retry_attempts_429=3,
    ):
        self.min_liquidity_usd = min_liquidity_usd
        self.min_daily_tx = min_daily_tx
        self.max_pages_per_dex = max_pages_per_dex
        self.sort_by = sort_by
        self.sort_ascending = sort_ascending
        self.output_csv = output_csv

        # Rate limiting controls
        self.calls_per_min_cap = calls_per_min_cap
        self.sleep_between_pages = sleep_between_pages
        self.sleep_between_dexes = sleep_between_dexes
        self.retry_attempts_429 = retry_attempts_429

        # Your requested default targets
        self.default_targets = [
            ("solana",    "orca"),
            ("solana",    "raydium"),
            ("base",      "aerodrome-slipstream"),
            #("bsc",       "pancakeswap-v3"),
        ]

    def _rate_limit_sleep(self):
        time.sleep(self.sleep_between_pages + random.uniform(0, 2.0))

    def _fetch_page(self, network, dex, page):
        url = f"https://api.geckoterminal.com/api/v2/networks/{network}/dexes/{dex}/pools"
        params = {"page": page, "limit": 100}

        for attempt in range(self.retry_attempts_429 + 1):
            try:
                resp = requests.get(url, params=params, timeout=15)

                if resp.status_code == 429:
                    wait = 60 * (2 ** attempt) + random.randint(5, 15)
                    print(f"  429 → waiting {wait}s (attempt {attempt+1}/{self.retry_attempts_429+1})")
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])

            except requests.exceptions.HTTPError as e:
                print(f"HTTP error {network}/{dex} page {page}: {e}")
                if attempt == self.retry_attempts_429:
                    return []
            except Exception as e:
                print(f"Unexpected error {network}/{dex} page {page}: {e}")
                return []

        return []

    def scan_dex(self, network, dex):
        collected = []
        call_count = 0

        print(f"  Starting {network}/{dex}  (up to {self.max_pages_per_dex} pages)")

        for page in range(1, self.max_pages_per_dex + 1):
            pools = self._fetch_page(network, dex, page)
            if not pools:
                break

            for p in pools:
                attrs = p.get("attributes", {})
                liq = float(attrs.get("liquidity_usd") or attrs.get("reserve_in_usd", 0))
                vol_h24 = float(attrs.get("volume_usd", {}).get("h24", 0))
                tx = attrs.get("transactions", {}).get("h24", {})
                daily_tx = (tx.get("buys", 0) or 0) + (tx.get("sells", 0) or 0)

                if liq >= self.min_liquidity_usd and daily_tx >= self.min_daily_tx:
                    collected.append({
                        "network": network,
                        "dex": dex,
                        "pool_address": p.get("id"),
                        "name": attrs.get("name", ""),
                        "symbol": attrs.get("symbol", ""),
                        "liquidity_usd": liq,
                        "volume_h24_usd": vol_h24,
                        "daily_tx": daily_tx,
                        "buys_24h": tx.get("buys", 0),
                        "sells_24h": tx.get("sells", 0),
                        "url": f"https://www.geckoterminal.com/{network}/pools/{p.get('id')}"
                    })

            print(f"    page {page:2d} : {len(pools):3d} pools fetched   |   matches so far: {len(collected):3d}")
            self._rate_limit_sleep()
            call_count += 1
            if call_count >= self.calls_per_min_cap:
                print("    Approaching call cap → pausing 60s")
                time.sleep(60)
                call_count = 0

        print(f"  Finished {network}/{dex}  → {len(collected)} pools matched criteria\n")
        return collected

    def scan(self, targets=None):
        if targets is None:
            targets = self.default_targets

        print("Starting GeckoTerminal pool scan...")
        print(f"Criteria: liquidity ≥ ${self.min_liquidity_usd:,}   |   daily tx ≥ {self.min_daily_tx:,}")
        print(f"Targets: {len(targets)} DEXes   |   max pages per DEX: {self.max_pages_per_dex}\n")

        all_matches = []

        for i, (net, dex) in enumerate(targets, 1):
            print(f"[{i}/{len(targets)}]  Scanning {net}/{dex}")
            matches = self.scan_dex(net, dex)
            all_matches.extend(matches)
            time.sleep(self.sleep_between_dexes + random.uniform(0, 5))

        if not all_matches:
            print("No pools found matching the current criteria.")
            return pd.DataFrame()

        df = pd.DataFrame(all_matches)
        df = df.sort_values(self.sort_by, ascending=self.sort_ascending)

        print(f"\nCompleted scan — found {len(df)} qualifying pools")
        print(f"Top 15 sorted by {self.sort_by} {'(descending)' if not self.sort_ascending else '(ascending)'}:\n")
        print(df.head(15)[[
            "network", "dex", "name",
            "liquidity_usd", "volume_h24_usd",
            "daily_tx", "buys_24h", "sells_24h"
        ]].to_string(index=False))

        df.to_csv(self.output_csv, index=False)
        print(f"\nFull results saved to: {self.output_csv}")
        print("Done.\n")

        return df


# ────────────────────────────────────────────────
if __name__ == "__main__":
    scanner = GeckoPoolScanner(
        min_liquidity_usd=1_000_000,
        min_daily_tx=10_000,
        max_pages_per_dex=5,           # feel free to increase to 15–20 if you want deeper results
        sleep_between_pages=7.5,
        sleep_between_dexes=18.0,
        calls_per_min_cap=20,
    )

    # Run with your requested DEXes (already set as default)
    scanner.scan()
