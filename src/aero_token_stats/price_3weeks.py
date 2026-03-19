from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import time
import sys


class AeroPriceFetcher:
    def __init__(self, symbol='AERO/USDC', timeframe='5m', weeks=3,
                 pool_address=None, limit=1000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.weeks = weeks
        self.pool_address = pool_address or "0x6cdcb1c4a4d1c3c6d054b27ac5b77e89eafb971d"
        self.limit = limit
        self.network = "base"
        self.aggregate = int(timeframe[:-1]) if timeframe.endswith("m") else 1

    def fetch_and_save(self):
        tf_minutes = int(self.timeframe[:-1])
        candles_per_day = 24 * 60 // tf_minutes
        expected_candles = int(self.weeks * 7 * candles_per_day * 0.95)
        
        target_date = datetime.now(timezone.utc) - timedelta(weeks=self.weeks + 0.2)
        target_since = int(target_date.timestamp())
        
        print(f"🎯 Target: {self.timeframe} candles for {self.weeks} weeks (~{expected_candles:,} candles)")
        print(f"📍 Will stop around {target_date.date()}")
        print(f"📍 Using Aerodrome pool: {self.pool_address}")
        print("⚠️  Smart early-stop + rate-limit handling enabled")

        all_ohlcv = []
        before = None
        total_fetched = 0
        retries = 0
        max_retries = 8

        while True:
            url = (
                f"https://api.geckoterminal.com/api/v2/networks/{self.network}/"
                f"pools/{self.pool_address}/ohlcv/minute"
                f"?aggregate={self.aggregate}&limit={self.limit}"
            )
            if before is not None:
                url += f"&before_timestamp={before}"

            print(f"🔄 Fetching page... (before={before})")
            
            try:
                r = requests.get(url, timeout=20)
                
                if r.status_code == 429:
                    wait_time = 30 + (retries * 15)
                    print(f"  ⏳ Rate limit hit. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    retries += 1
                    if retries > max_retries:
                        print("  ⚠️  Max retries reached — stopping.")
                        break
                    continue

                r.raise_for_status()
                data = r.json()
                
                ohlcv_list = data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
                if not ohlcv_list:
                    break

                all_ohlcv = ohlcv_list + all_ohlcv
                total_fetched += len(ohlcv_list)

                oldest_ts = ohlcv_list[-1][0]
                oldest_dt = datetime.fromtimestamp(oldest_ts, tz=timezone.utc)

                if oldest_ts < target_since:
                    print(f"  ✅ Reached {self.weeks}-week target (oldest: {oldest_dt.date()}). Stopping.")
                    break

                before = oldest_ts - 1

                print(f"  → Fetched {len(ohlcv_list)} | Total: {total_fetched:,}")

                if len(ohlcv_list) < self.limit - 100:
                    break

                time.sleep(10)

            except Exception as e:
                print(f"  ❌ Error: {e}")
                break

        if not all_ohlcv:
            print("❌ No data received.")
            return None

        # Build DataFrame with proper timezone handling
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df = df.drop_duplicates(subset=['timestamp'])
        df = df.sort_values('timestamp')
        
        # Make index UTC-aware for correct trimming
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
        df = df.set_index('datetime').drop(columns=['timestamp'])

        # Safety trim (both now aware)
        cutoff = target_date - timedelta(days=1)
        df = df[df.index >= cutoff]

        # Convert back to naive so it works perfectly with draw_chart.py
        df.index = df.index.tz_convert(None)

        print(f"\n✅ DONE! {len(df):,} {self.timeframe} candles")
        print(f"Period: {df.index[0].date()} → {df.index[-1].date()}")

        filename = f"AERO_{self.timeframe}_{self.weeks}weeks_aerodrome.csv"
        df.to_csv(filename)
        print(f"💾 Saved → {filename}")

        return df


# ========================= CLI =========================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            minutes = int(sys.argv[1])
            timeframe = f"{minutes}m"
            print(f"🛠️ Using {timeframe}")
        except:
            timeframe = '5m'
    else:
        timeframe = '5m'

    fetcher = AeroPriceFetcher(timeframe=timeframe)
    fetcher.fetch_and_save()
