import requests
import pandas as pd
import time
import os  # for existing file detection
from datetime import datetime, timezone, timedelta
from typing import Optional, List

# ────────────────────────────────────────────────
# Matplotlib with graceful fallback (chart feature)
# ────────────────────────────────────────────────
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not installed. Charts will be skipped.")
    print("   Run: pip install matplotlib\n")


class AerodromeSlipstreamFetcher:
    """
    Fetcher for Aerodrome Slipstream pools (Geckoterminal API).
    Features:
      • Auto-detects symbols + TVL
      • Smart resume (y/n prompt)
      • Clean PNG chart with TVL: $864,690 format (no "Latest" or candle count)
      • DPI=150 for small file sizes
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
            print(f"   TVL: ${self.tvl_usd:,.0f}")
            print(f"   (name: {data.get('name', 'N/A')})\n")

        except Exception as e:
            print(f"⚠️  Could not fetch pool metadata: {e}")
            self.base_symbol = "BASE"
            self.quote_symbol = "QUOTE"
            self.tvl_usd = 0.0

    def _fetch_batch(self, currency: str, before_ts: Optional[int] = None, aggregate: int = 15, limit: int = 500, retries: int = 5) -> List[list]:
        for attempt in range(retries + 1):
            params = {"aggregate": aggregate, "limit": limit, "currency": currency}
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

        return []

    def _create_price_chart(self, df: pd.DataFrame, aggregate: int):
        """Clean PNG chart — DPI 150 + ultra-simple title (TVL: $864,690 only)"""
        if df.empty or not MATPLOTLIB_AVAILABLE:
            return

        base_col = f"close_{self.base_symbol.lower()}_usd"
        chart_filename = f"aerodrome_{self.base_symbol}_{self.quote_symbol}_{aggregate}min_chart.png".lower()

        fig, ax1 = plt.subplots(figsize=(14, 7))
        color = 'tab:blue'
        ax1.set_xlabel('Date (UTC)')
        ax1.set_ylabel(f'{self.base_symbol} Price (USD)', color=color)
        ax1.plot(df.index, df[base_col], color=color, linewidth=2)
        ax1.tick_params(axis='y', labelcolor=color)

        ax2 = ax1.twinx()
        color = 'tab:gray'
        ax2.set_ylabel('Volume (USD)', color=color)
        width = pd.Timedelta(minutes=aggregate * 0.9)
        ax2.bar(df.index, df['volume_usd'], color=color, alpha=0.4, width=width)
        ax2.tick_params(axis='y', labelcolor=color)

        # UPDATED TITLE: exactly what you asked for (super clean)
        plt.title(
            f"{self.base_symbol} / {self.quote_symbol} — {aggregate}-min Candles\n"
            f"TVL: ${self.tvl_usd:,.0f}"
        )
        fig.tight_layout()
        plt.grid(True, alpha=0.3)
        plt.savefig(chart_filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Chart saved → {chart_filename}  (small file size)")

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

        # Smart resume: Existing CSV detection + y/n prompt
        kst_tz = timezone(timedelta(hours=9))

        if os.path.exists(filename):
            mod_ts = os.path.getmtime(filename)
            mod_dt_utc = datetime.fromtimestamp(mod_ts, tz=timezone.utc)
            mod_dt_kst = mod_dt_utc.astimezone(kst_tz)
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)

            print(f"\n📁 Existing data found: {filename}")
            print(f"   Last modified: {mod_dt_kst:%Y-%m-%d %H:%M KST}")
            print(f"   Size: {file_size_mb:.1f} MB")
            print(f"   Current TVL (refreshed): ${self.tvl_usd:,.0f}")

            choice = input("   Use existing data and skip download? (y/n) → ").strip().lower()
            if choice in ("y", "yes"):
                print("✅ Loading existing CSV...")
                try:
                    df = pd.read_csv(filename, index_col="datetime", parse_dates=True)
                    print(f"   Loaded {len(df):,} candles (range: {df.index[0]} → {df.index[-1]})")
                    
                    self._create_price_chart(df, aggregate)
                    return df
                except Exception as e:
                    print(f"⚠️  Could not load CSV ({e}) — falling back to fresh download.")

        # Fresh download logic
        print("📥 Fetching fresh data from GeckoTerminal API...\n")

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

            print(f"Page {page+1:3d} | {dt_latest:%Y-%m-%d %H:%M} → {dt_oldest:%Y-%m-%d}")

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

        df_usd = pd.DataFrame(all_usd, columns=["timestamp", "open_usd", "high_usd", "low_usd", "close_usd", "volume_usd"])
        df_ratio = pd.DataFrame(all_ratio, columns=["timestamp", "open_ratio", "high_ratio", "low_ratio", "close_ratio", "volume_ratio"])

        df = pd.merge(df_usd, df_ratio, on="timestamp", how="inner")
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = df.set_index("datetime").sort_index()

        base_col = f"close_{self.base_symbol.lower()}_usd"
        quote_col = f"close_{self.quote_symbol.lower()}_usd"

        df[base_col] = df["close_usd"]
        df[quote_col] = df["close_usd"] / df["close_ratio"]

        # Final summary
        if not df.empty:
            latest_utc = df.index[-1]
            latest_kst = latest_utc.astimezone(kst_tz)

            print(f"\nRange:     {df.index[0]} → {latest_utc} UTC")
            print(f"           ({latest_kst.strftime('%Y-%m-%d %H:%M KST')})")
            print(f"Latest:    1 {self.base_symbol} ≈ ${df['close_usd'].iloc[-1]:,.2f}")
            print(f"           = {df['close_ratio'].iloc[-1]:.6f} {self.quote_symbol}")
            print(f"           ({self.quote_symbol} ≈ ${df[quote_col].iloc[-1]:,.0f})")
            print(f"Candles:   {len(df):,}")
            print(f"TVL:       ${self.tvl_usd:,.0f}")
            print(f"File size: ~{len(df) * 0.00035:.1f} MB")

        if save_csv and not df.empty:
            df.to_csv(filename)
            print(f"\n💾 Saved → {filename}")
            self._create_price_chart(df, aggregate)

        return df


# ────────────────────────────────────────────────
if __name__ == "__main__":
    DEFAULT_POOL = "0x22aee3699b6a0fed71490c103bd4e5f3309891d5"   # WETH–cbBTC

    print("\n" + "="*85)
    print("🚀 Aerodrome Slipstream Historic Price Fetcher + Chart + TVL + Smart Resume")
    print("="*85)
    print(f"Default pool: {DEFAULT_POOL} (WETH / cbBTC)\n")

    user_input = input("Enter Aerodrome pool contract address (0x...) or press Enter for default\n→ ").strip()
    POOL = user_input if user_input else DEFAULT_POOL

    fetcher = AerodromeSlipstreamFetcher(POOL)

    df = fetcher.fetch_recent(
        days_back=179,
        aggregate=15,
        save_csv=True
    )

    if not df.empty:
        base_col = f"close_{fetcher.base_symbol.lower()}_usd"
        print("\nLast 5 candles:")
        print(df[[base_col, "close_ratio", f"close_{fetcher.quote_symbol.lower()}_usd", "volume_usd"]].tail(5))
