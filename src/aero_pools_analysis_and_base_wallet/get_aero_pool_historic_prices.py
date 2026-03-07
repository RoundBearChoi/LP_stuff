import requests
import pandas as pd
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, List


class AerodromeSlipstreamFetcher:
    """
    Fetcher for Aerodrome Slipstream pools (Geckoterminal API).
    Now dynamically detects base/quote token symbols from the pool contract info.
    Works for ANY 2-token pool — no hardcoding needed.
    """

    def __init__(self, pool_address: str, network: str = "base"):
        self.pool_address = pool_address.lower()
        self.network = network
        self.base_url = (
            f"https://api.geckoterminal.com/api/v2/networks/{network}/"
            f"pools/{self.pool_address}/ohlcv/minute"
        )
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        # Populated automatically
        self.base_symbol: str = "UNKNOWN"
        self.quote_symbol: str = "UNKNOWN"

    def _fetch_pool_info(self):
        """One-time fetch of pool metadata to extract real token symbols"""
        url = (
            f"https://api.geckoterminal.com/api/v2/networks/{self.network}/"
            f"pools/{self.pool_address}"
        )
        try:
            resp = self.session.get(url, timeout=12)
            resp.raise_for_status()
            data = resp.json()["data"]["attributes"]
            pool_name = data.get("pool_name") or data.get("name", "")

            if " / " in pool_name:
                parts = [p.strip() for p in pool_name.split(" / ", 1)]
                self.base_symbol = parts[0]
                self.quote_symbol = parts[1]
            else:
                self.base_symbol = "BASE"
                self.quote_symbol = "QUOTE"

            print(f"✅ Pool detected: {self.base_symbol} / {self.quote_symbol}")
            print(f"   (name: {data.get('name', 'N/A')})\n")

        except Exception as e:
            print(f"⚠️  Could not fetch pool metadata: {e}")
            print("   Falling back to generic names (script will still work)\n")
            self.base_symbol = "BASE"
            self.quote_symbol = "QUOTE"

    def _fetch_batch(
        self,
        currency: str,
        before_ts: Optional[int] = None,
        aggregate: int = 15,
        limit: int = 500,
        retries: int = 5
    ) -> List[list]:
        for attempt in range(retries + 1):
            params = {
                "aggregate": aggregate,
                "limit": limit,
                "currency": currency,
            }
            if before_ts is not None:
                params["before_timestamp"] = before_ts

            try:
                resp = self.session.get(self.base_url, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])

            except requests.exceptions.HTTPError as e:
                if getattr(resp, "status_code", 0) == 429:
                    wait = (2 ** attempt) * 5 + 2
                    print(f"Rate limit (429). Sleeping {wait}s (attempt {attempt+1}/{retries})")
                    time.sleep(wait)
                    continue
                print(f"HTTP {getattr(resp, 'status_code', '???')} ({currency}): {resp.text[:180]}")
                return []

            except Exception as e:
                print(f"Request failed ({currency}): {str(e)}")
                return []

        print(f"Failed after {retries} retries — currency={currency}")
        return []

    def fetch_recent(
        self,
        days_back: float = 179.0,
        aggregate: int = 15,
        save_csv: bool = True,
        filename: Optional[str] = None,
        max_pages: int = 400
    ) -> pd.DataFrame:
        if self.base_symbol == "UNKNOWN":
            self._fetch_pool_info()

        if filename is None:
            filename = f"aerodrome_{self.base_symbol}_{self.quote_symbol}_{aggregate}min_recent.csv".lower()

        now_ts = int(time.time())
        cutoff_ts = now_ts - int(days_back * 86400)
        cutoff_date_str = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).strftime("%Y-%m-%d")

        print(f"Fetching ≈ {days_back:.1f} days of {aggregate}-minute candles")
        print(f"→ Data before {cutoff_date_str} UTC will be ignored")
        print(f"Output file: {filename}\n")

        all_usd: List[list] = []
        all_ratio: List[list] = []
        before_ts: Optional[int] = None
        page = 0

        kst_tz = timezone(timedelta(hours=9))

        while page < max_pages:
            batch_usd = self._fetch_batch("usd", before_ts, aggregate)
            batch_ratio = self._fetch_batch("token", before_ts, aggregate)

            if not batch_usd or not batch_ratio:
                print("Reached end of available data from API.")
                break

            ts_latest = batch_usd[0][0]
            ts_oldest = batch_usd[-1][0]

            dt_latest = datetime.fromtimestamp(ts_latest, tz=timezone.utc)
            dt_oldest = datetime.fromtimestamp(ts_oldest, tz=timezone.utc)

            print(
                f"Page {page+1:3d} | "
                f"{dt_latest:%Y-%m-%d %H:%M} → {dt_oldest:%Y-%m-%d}"
            )

            batch_usd = [c for c in batch_usd if c[0] >= cutoff_ts]
            batch_ratio = [c for c in batch_ratio if c[0] >= cutoff_ts]

            all_usd.extend(batch_usd)
            all_ratio.extend(batch_ratio)

            if ts_oldest < cutoff_ts:
                print("Reached desired time range → stopping early.")
                break

            before_ts = ts_oldest - 1
            page += 1

            if len(batch_usd) < 450:
                break

            time.sleep(2.3)

        if not all_usd:
            print("\nNo data was retrieved.")
            return pd.DataFrame()

        df_usd = pd.DataFrame(
            all_usd,
            columns=["timestamp", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"]
        )
        df_ratio = pd.DataFrame(
            all_ratio,
            columns=["timestamp", "open_ratio", "high_ratio", "low_ratio", "close_ratio", "volume_ratio"]
        )

        df = pd.merge(df_usd, df_ratio, on="timestamp", how="inner")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = df.set_index("datetime").sort_index()

        base_col = f"close_{self.base_symbol.lower()}_usd"
        quote_col = f"close_{self.quote_symbol.lower()}_usd"

        df[base_col] = df["close_usd"]
        df[quote_col] = df["close_usd"] / df["close_ratio"]

        if not df.empty:
            latest_utc = df.index[-1]
            latest_kst = latest_utc.astimezone(kst_tz)

            print(f"\nRange:     {df.index[0]} → {latest_utc} UTC")
            print(f"           ({latest_kst.strftime('%Y-%m-%d %H:%M KST')})")
            print(f"Latest:    1 {self.base_symbol} ≈ ${df['close_usd'].iloc[-1]:,.2f}")
            print(f"           = {df['close_ratio'].iloc[-1]:.6f} {self.quote_symbol}")
            print(f"           ({self.quote_symbol} ≈ ${df[quote_col].iloc[-1]:,.0f})")
            print(f"Candles:   {len(df):,}")
            print(f"File size: ~{len(df) * 0.00035:.1f} MB (rough estimate)")

        if save_csv:
            df.to_csv(filename)
            print(f"\nSaved → {filename}")

        return df


# ────────────────────────────────────────────────
if __name__ == "__main__":
    DEFAULT_POOL = "0x22aee3699b6a0fed71490c103bd4e5f3309891d5"   # WETH–cbBTC

    print("\n" + "="*70)
    print("🚀 Aerodrome Slipstream Historic Price Fetcher")
    print("="*70)
    print(f"Default pool: {DEFAULT_POOL} (WETH / cbBTC)\n")

    user_input = input(
        "Enter Aerodrome pool contract address (0x...)\n"
        "   (or just press Enter to use default)\n"
        "→ "
    ).strip()

    if user_input:
        POOL = user_input
        print(f"✅ Using provided pool: {POOL}\n")
    else:
        POOL = DEFAULT_POOL
        print(f"✅ Using default pool: {DEFAULT_POOL} (WETH / cbBTC)\n")

    # Quick validation (helps catch typos)
    if not POOL.startswith("0x") or len(POOL) != 42:
        print("⚠️  Warning: Address doesn't look like a valid 0x address.")
        print("   Continuing anyway...\n")

    fetcher = AerodromeSlipstreamFetcher(POOL)

    df = fetcher.fetch_recent(
        days_back=179,
        aggregate=15,
        save_csv=True
    )

    if not df.empty:
        base_col = f"close_{fetcher.base_symbol.lower()}_usd"
        quote_col = f"close_{fetcher.quote_symbol.lower()}_usd"
        print("\nLast 5 candles:")
        print(df[[base_col, "close_ratio", quote_col, "volume_usd"]].tail(5))
