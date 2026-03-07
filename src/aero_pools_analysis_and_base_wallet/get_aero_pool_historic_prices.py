import requests
import pandas as pd
import time
import os
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
      • Clean PNG chart showing BASE/QUOTE ratio (instead of base USD price) + TVL
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
        """Clean PNG chart — NOW SHOWS the BASE/QUOTE ratio on the primary Y-axis"""
        if df.empty or not MATPLOTLIB_AVAILABLE:
            return

        chart_filename = f"aerodrome_{self.base_symbol}_{self.quote_symbol}_{aggregate}min_chart.png".lower()

        fig, ax1 = plt.subplots(figsize=(14, 7))
        color = 'tab:blue'
        ax1.set_xlabel('Date (UTC)')
        
        # === UPDATED: Plot ratio (already in CSV) instead of WETH USD price ===
        ax1.set_ylabel(f'{self.base_symbol} / {self.quote_symbol} Ratio', color=color)
        ax1.plot(df.index, df["close_ratio"], color=color, linewidth=2.2)
        ax1.tick_params(axis='y', labelcolor=color)
        
        # Clean formatting for typical crypto ratios (~0.02xxx)
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.6f}'))

        ax2 = ax1.twinx()
        color = 'tab:gray'
        ax2.set_ylabel('Volume (USD)', color=color)
        width = pd.Timedelta(minutes=aggregate * 0.9)
        ax2.bar(df.index, df['volume_usd'], color=color, alpha=0.4, width=width)
        ax2.tick_params(axis='y', labelcolor=color)

        plt.title(
            f"{self.base_symbol} / {self.quote_symbol} Ratio — {aggregate}-min Candles\n"
            f"TVL: ${self.tvl_usd:,.0f}"
        )
        fig.tight_layout()
        plt.grid(True, alpha=0.3)
        plt.savefig(chart_filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Ratio chart saved → {chart_filename}  (small file size)")

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

        # Smart resume logic (unchanged)
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

        # Fresh download logic (unchanged — full method omitted here for brevity; copy from your original if needed)
        # ... [the entire fresh download block from your original script stays 100% identical] ...

        # (The rest of fetch_recent — data processing, column creation, printing, saving — is unchanged)
        # For completeness, the final part is shown below with a tiny cleanup:

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
    print("🚀 Aerodrome Slipstream Historic Price Fetcher + Ratio Chart + TVL + Smart Resume")
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
        print("\nLast 5 candles:")
        print(df[["close_ratio", f"close_{fetcher.quote_symbol.lower()}_usd", "volume_usd"]].tail(5))
