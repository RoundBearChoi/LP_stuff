import requests
import pandas as pd
import time
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import numpy as np

# Matplotlib fallback
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not installed. Charts will be skipped.")
    print("   Run: pip install matplotlib\n")


class AerodromeSlipstreamFetcher:
    """
    FIXED VERSION - Now fully compatible with analyze_aero_pool_historic_prices.py
    • Saves high_usd / low_usd / open_usd (required by analyzer)
    • Full-depth USD fetching (no more artificial page limit)
    • Proper datetime index name for CSV
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

        self.base_symbol: str = "UNKNOWN"
        self.quote_symbol: str = "UNKNOWN"
        self.tvl_usd: float = 0.0

    def _fetch_pool_info(self):
        """One-time fetch of pool metadata (symbols + TVL)"""
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

            self.tvl_usd = float(data.get("reserve_in_usd", 0) or 0)

            print(f"✅ Pool detected: {self.base_symbol} / {self.quote_symbol}")
            print(f"   TVL: ${self.tvl_usd:,.0f}\n")

        except Exception as e:
            print(f"⚠️  Could not fetch pool metadata: {e}")
            self.base_symbol = "BASE"
            self.quote_symbol = "QUOTE"
            self.tvl_usd = 0.0

    def _fetch_batch(self, currency: str = "usd", token_param: Optional[str] = None,
                     before_ts: Optional[int] = None, aggregate: int = 15,
                     limit: int = 500, retries: int = 5) -> List[list]:
        """Fetch one batch (enhanced rate-limit handling)"""
        for attempt in range(retries + 1):
            params = {"aggregate": aggregate, "limit": limit, "currency": currency}
            if token_param:
                params["token"] = token_param
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
                    print(f"   Rate limit (429). Sleeping {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"HTTP {getattr(resp, 'status_code', '???')}: {str(e)[:150]}")
                return []
            except Exception as e:
                print(f"Request failed ({currency}): {e}")
                if attempt == retries:
                    return []
                time.sleep(2 ** attempt)
        return []

    def _create_price_chart(self, df: pd.DataFrame, aggregate: int):
        """Clean PNG chart (unchanged logic, just uses close_ratio)"""
        if df.empty or not MATPLOTLIB_AVAILABLE:
            return

        chart_filename = f"aerodrome_{self.base_symbol}_{self.quote_symbol}_{aggregate}min_chart.png".lower()

        fig, ax1 = plt.subplots(figsize=(14, 7))
        color = 'tab:blue'
        ax1.set_xlabel('Date (UTC)')
        ax1.set_ylabel(f'{self.base_symbol} / {self.quote_symbol} Ratio', color=color)
        ax1.plot(df.index, df["close_ratio"], color=color, linewidth=2.2)
        ax1.tick_params(axis='y', labelcolor=color)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.6f}'))

        ax2 = ax1.twinx()
        color = 'tab:gray'
        ax2.set_ylabel('Volume (USD)', color=color)
        width = pd.Timedelta(minutes=aggregate * 0.9)
        ax2.bar(df.index, df['volume_usd'], color=color, alpha=0.4, width=width)
        ax2.tick_params(axis='y', labelcolor=color)

        plt.title(
            f"{self.base_symbol} / {self.quote_symbol} Ratio — {aggregate}-min Candles\n"
            f"TVL: ${self.tvl_usd:,.0f} | {len(df):,} candles"
        )
        fig.tight_layout()
        plt.grid(True, alpha=0.3)
        plt.savefig(chart_filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Ratio chart saved → {chart_filename}")

    def fetch_recent(
        self,
        days_back: float = 179.0,
        aggregate: int = 15,
        save_csv: bool = True,
        filename: Optional[str] = None,
        max_pages: int = 600
    ) -> pd.DataFrame:

        if self.base_symbol == "UNKNOWN":
            self._fetch_pool_info()

        if filename is None:
            filename = f"aerodrome_{self.base_symbol.lower()}_{self.quote_symbol.lower()}_{aggregate}min_recent.csv"

        # ====================== SMART RESUME ======================
        if os.path.exists(filename):
            mod_ts = os.path.getmtime(filename)
            mod_dt_utc = datetime.fromtimestamp(mod_ts, tz=timezone.utc)
            mod_dt_kst = mod_dt_utc.astimezone(timezone(timedelta(hours=9)))
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)

            print(f"\n📁 Existing data found: {filename}")
            print(f"   Last modified: {mod_dt_kst:%Y-%m-%d %H:%M KST}")
            print(f"   Size: {file_size_mb:.1f} MB")
            print(f"   Current TVL: ${self.tvl_usd:,.0f}")

            choice = input("   Use existing data and skip download? (y/n) → ").strip().lower()
            if choice in ("y", "yes", ""):
                print("✅ Loading existing CSV...")
                try:
                    df = pd.read_csv(filename, index_col="datetime", parse_dates=True)
                    print(f"   Loaded {len(df):,} candles")
                    self._create_price_chart(df, aggregate)
                    return df
                except Exception as e:
                    print(f"⚠️  Could not load CSV ({e}) — falling back to download.")

        # ====================== FRESH DOWNLOAD ======================
        print(f"\n🔄 Starting fresh download ({aggregate}min candles, {days_back:.0f} days)...")
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

        # 1. Fetch BASE/QUOTE ratio
        print("   Fetching BASE/QUOTE ratio...")
        ratio_batches = []
        before_ts: Optional[int] = None
        page = 0

        while page < max_pages:
            page += 1
            batch = self._fetch_batch(
                currency="token",
                token_param="base",
                before_ts=before_ts,
                aggregate=aggregate
            )
            if not batch:
                break

            temp = pd.DataFrame(batch, columns=["ts", "open_ratio", "high_ratio", "low_ratio", "close_ratio", "volume_quote"])
            temp["datetime"] = pd.to_datetime(temp["ts"], unit="s", utc=True)
            temp = temp.set_index("datetime").sort_index()
            ratio_batches.append(temp[["open_ratio", "high_ratio", "low_ratio", "close_ratio", "volume_quote"]])
            before_ts = int(temp.index[0].timestamp()) - 30

            print(f"   Ratio Page {page:3d} | {len(temp):4d} candles | oldest: {temp.index[0].strftime('%Y-%m-%d')}")
            if temp.index[0] < cutoff:
                break
            time.sleep(0.35)

        # 2. Fetch FULL USD OHLC (this was the main bug)
        print("   Fetching full USD OHLC + volume...")
        usd_batches = []
        before_ts = None
        page = 0

        while page < max_pages:
            page += 1
            batch = self._fetch_batch(currency="usd", before_ts=before_ts, aggregate=aggregate)
            if not batch:
                break

            temp = pd.DataFrame(batch, columns=["ts", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"])
            temp["datetime"] = pd.to_datetime(temp["ts"], unit="s", utc=True)
            temp = temp.set_index("datetime").sort_index()
            usd_batches.append(temp[["open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"]])

            before_ts = int(temp.index[0].timestamp()) - 30

            print(f"   USD Page {page:3d} | {len(temp):4d} candles | oldest: {temp.index[0].strftime('%Y-%m-%d')}")
            if temp.index[0] < cutoff:
                break
            time.sleep(0.35)

        # Combine
        if not ratio_batches:
            print("❌ No data returned by API.")
            return pd.DataFrame()

        df_ratio = pd.concat(ratio_batches).sort_index()
        df_usd = pd.concat(usd_batches).sort_index() if usd_batches else pd.DataFrame()

        df = df_ratio.join(df_usd, how="left")
        df = df[~df.index.duplicated(keep="first")]

        # Derive quote USD price
        quote_col = f"close_{self.quote_symbol.lower()}_usd"
        df[quote_col] = df["close_usd"] / df["close_ratio"].replace(0, np.nan)

        # CRITICAL for analyzer
        df.index.name = "datetime"

        # ====================== FINAL OUTPUT ======================
        if not df.empty:
            latest_utc = df.index[-1]
            latest_kst = latest_utc.astimezone(timezone(timedelta(hours=9)))

            print(f"\nRange:     {df.index[0]} → {latest_utc} UTC")
            print(f"           ({latest_kst.strftime('%Y-%m-%d %H:%M KST')})")
            print(f"Latest:    1 {self.base_symbol} ≈ ${df['close_usd'].iloc[-1]:,.2f}")
            print(f"           = {df['close_ratio'].iloc[-1]:.6f} {self.quote_symbol}")
            print(f"Candles:   {len(df):,}")
            print(f"TVL:       ${self.tvl_usd:,.0f}")

        if save_csv and not df.empty:
            df.to_csv(filename)
            print(f"\n💾 Saved → {filename}")
            self._create_price_chart(df, aggregate)

        return df


# ────────────────────────────────────────────────
if __name__ == "__main__":
    DEFAULT_POOL = "0x22aee3699b6a0fed71490c103bd4e5f3309891d5"   # WETH–cbBTC

    print("\n" + "="*90)
    print("🚀 Aerodrome Slipstream Historic Price Fetcher (FIXED + Analyzer Ready)")
    print("="*90)
    print(f"Default pool: {DEFAULT_POOL} (WETH / cbBTC)\n")

    user_input = input("Enter Aerodrome pool contract address (0x...) or press Enter for default\n→ ").strip()
    POOL = user_input if user_input else DEFAULT_POOL

    fetcher = AerodromeSlipstreamFetcher(POOL)

    df = fetcher.fetch_recent(
        days_back=179,
        aggregate=15,
        save_csv=True,
        max_pages=600
    )

    if not df.empty:
        print("\nLast 5 candles:")
        quote_col = f"close_{fetcher.quote_symbol.lower()}_usd"
        print(df[["close_ratio", "close_usd", quote_col, "high_usd", "low_usd", "volume_usd"]].tail(5))
