import requests
import pandas as pd
import time
import os
from datetime import datetime, timezone, timedelta
from typing import Optional


class AerodromeSlipstreamFetcher:
    """
    Robust fetcher for Aerodrome Slipstream pools.
    Features:
      • Automatic incremental updates (only fetches new candles since your last CSV entry)
      • Full history on first run (capped at max_years)
      • Perfect compatibility with your existing CSV (timezone-aware fix included)
      • Safe, rate-limit friendly, no duplicates
    """

    def __init__(self, pool_address: str, network: str = "base"):
        self.pool_address = pool_address.lower()
        self.network = network
        self.base_url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/minute"
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _fetch_batch(self, currency: str, before_ts: Optional[int] = None, aggregate: int = 15, limit: int = 500, retries: int = 5) -> list:
        """Fetch one batch with smart retry on 429"""
        for attempt in range(retries + 1):
            params = {"aggregate": aggregate, "limit": limit, "currency": currency}
            if before_ts:
                params["before_timestamp"] = before_ts

            response = self.session.get(self.base_url, params=params)

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])

            if response.status_code == 429:
                wait = (2 ** attempt) * 5
                print(f" ⏳ Rate limit hit (429). Waiting {wait}s before retry {attempt+1}/{retries}...")
                time.sleep(wait)
                continue

            print(f"❌ Error {response.status_code} (currency={currency}): {response.text[:150]}")
            return []

        print(f"❌ Failed after {retries} retries for currency={currency}")
        return []

    def fetch_full_history(self, aggregate: int = 15, save_csv: bool = True, 
                           filename: Optional[str] = None, max_years: Optional[float] = 2.0) -> pd.DataFrame:
        """Fetch full history OR incrementally update existing CSV"""
        
        # === DETERMINE FILENAME ===
        if filename is None:
            max_part = f"max{max_years}y" if max_years is not None else "full"
            filename = f"aerodrome_{self.pool_address}_{aggregate}min_{max_part}.csv"

        # === LOAD EXISTING DATA IF PRESENT (incremental mode) ===
        existing_df = None
        last_known_ts = None
        is_update = False
        kst_tz = timezone(timedelta(hours=9))  # KST = UTC+9

        if os.path.exists(filename):
            print(f"📁 Existing data found → {filename}")
            existing_df = pd.read_csv(filename, index_col='datetime', parse_dates=True)
            
            # ← CRITICAL FIX: Make index timezone-aware (prevents pandas concat warnings)
            if existing_df.index.tz is None:
                existing_df.index = pd.to_datetime(existing_df.index, utc=True)
            
            # Get latest timestamp
            if 'timestamp' in existing_df.columns:
                last_known_ts = int(existing_df['timestamp'].max())
            else:
                last_known_ts = int(existing_df.index.astype('int64') // 10**9).max()
            
            last_utc = datetime.fromtimestamp(last_known_ts, tz=timezone.utc)
            last_kst = last_utc.astimezone(kst_tz)
            print(f"   Latest entry: {last_utc.strftime('%Y-%m-%d %H:%M')} UTC "
                  f"({last_kst.strftime('%Y-%m-%d %H:%M KST')})")
            print(f"   → Performing incremental update (only new candles since then)...")
            is_update = True
        else:
            print(f"🆕 No existing file → starting full fetch (capped at {max_years} years)")

        # === CUTOFF ONLY FOR INITIAL FULL FETCH ===
        cutoff_ts = None
        if max_years is not None and not is_update:
            cutoff_ts = int(time.time()) - int(max_years * 365.25 * 24 * 3600)
            cutoff_date = datetime.fromtimestamp(cutoff_ts, tz=timezone.utc).strftime('%Y-%m-%d')
            print(f"📅 Capping at max {max_years} years → ignoring before {cutoff_date}")

        # === FETCH LOOP ===
        all_usd = []
        all_ratio = []
        before_ts = None
        page = 0
        max_pages = 300

        print(f"🚀 Starting {'UPDATE' if is_update else 'FULL'} fetch for pool {self.pool_address[:10]}...")

        while page < max_pages:
            batch_usd = self._fetch_batch("usd", before_ts, aggregate)
            batch_ratio = self._fetch_batch("token", before_ts, aggregate)

            if not batch_usd or not batch_ratio:
                print("✅ Reached end of available data from API.")
                break

            batch_latest_ts = batch_usd[0][0]
            batch_oldest_ts = batch_usd[-1][0]

            first_date = datetime.fromtimestamp(batch_latest_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            oldest_date = datetime.fromtimestamp(batch_oldest_ts, tz=timezone.utc).strftime('%Y-%m-%d')
            print(f" Page {page + 1:2d}... {first_date} → {oldest_date}")

            # === FILTER / COLLECT NEW DATA ===
            if last_known_ts is not None:  # UPDATE MODE
                new_usd = [c for c in batch_usd if c[0] > last_known_ts]
                new_ratio = [c for c in batch_ratio if c[0] > last_known_ts]
                
                all_usd.extend(new_usd)
                all_ratio.extend(new_ratio)

                if len(new_usd) < len(batch_usd):  # we hit existing data
                    print(f"   → Reached existing data. Incremental fetch complete.")
                    break
            else:  # FULL MODE
                all_usd.extend(batch_usd)
                all_ratio.extend(batch_ratio)

                # Apply max_years cutoff
                if cutoff_ts is not None and batch_oldest_ts < cutoff_ts:
                    print(f"   → Hit {max_years}-year limit. Trimming...")
                    all_usd = [c for c in all_usd if c[0] >= cutoff_ts]
                    all_ratio = [c for c in all_ratio if c[0] >= cutoff_ts]
                    break

            before_ts = batch_oldest_ts - 1

            if len(batch_usd) < 400:
                break

            time.sleep(2.2)
            page += 1

        # === BUILD / MERGE DATAFRAME ===
        if all_usd:
            df_usd = pd.DataFrame(all_usd, columns=['timestamp', 'open_usd', 'high_usd', 'low_usd', 'close_usd', 'volume_usd'])
            df_ratio = pd.DataFrame(all_ratio, columns=['timestamp', 'open_ratio', 'high_ratio', 'low_ratio', 'close_ratio', 'volume_ratio'])

            df_new = pd.merge(df_usd, df_ratio, on='timestamp', how='inner')
            df_new['datetime'] = pd.to_datetime(df_new['timestamp'], unit='s', utc=True)
            df_new = df_new.set_index('datetime').sort_index()
            df_new['close_cbbtc_usd'] = df_new['close_usd'] / df_new['close_ratio']

            if existing_df is not None:
                df = pd.concat([existing_df, df_new])
                df = df[~df.index.duplicated(keep='last')].sort_index()
                print(f"\n✅ UPDATED! Added {len(df_new):,} new candles → Total: {len(df):,}")
            else:
                df = df_new
                print(f"\n✅ NEW full dataset: {len(df):,} candles")
        else:
            df = existing_df
            print("\n✅ No new data to add.")

        # Final summary (with KST for you)
        if not df.empty:
            latest_utc = df.index[-1]
            latest_kst = latest_utc.tz_convert(kst_tz) if hasattr(latest_utc, 'tz_convert') else latest_utc
            print(f"   Range: {df.index[0]} → {latest_utc} UTC ({latest_kst.strftime('%Y-%m-%d %H:%M KST')})")
            print(f"   Latest: 1 WETH = ${df['close_usd'].iloc[-1]:.2f} "
                  f"= {df['close_ratio'].iloc[-1]:.6f} cbBTC "
                  f"(cbBTC ≈ ${df['close_cbbtc_usd'].iloc[-1]:,.0f})")

        if save_csv:
            df.to_csv(filename)
            print(f"💾 Saved/Updated → {filename}")

        return df


# ====================== USAGE ======================
if __name__ == "__main__":
    fetcher = AerodromeSlipstreamFetcher("0x22aee3699b6a0fed71490c103bd4e5f3309891d5")
    
    df = fetcher.fetch_full_history(max_years=2.0)  # first run = full; next runs = auto-update

    print("\nLast 3 rows preview:")
    print(df[['close_usd', 'close_ratio', 'close_cbbtc_usd', 'volume_usd']].tail(3))
