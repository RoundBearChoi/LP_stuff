from datetime import datetime, timedelta, timezone
import ccxt
import pandas as pd
import time
import sys


class AeroPriceFetcher:
    def __init__(self, symbol='AERO/USDT', timeframe='5m', weeks=3,
                 exchanges_to_try=None, limit=1000):
        self.symbol = symbol
        self.timeframe = timeframe
        self.weeks = weeks
        self.exchanges_to_try = exchanges_to_try or ['bybit', 'mexc', 'gate']
        self.limit = limit

    def fetch_and_save(self):
        # Auto-calculate expected candles
        tf_minutes = int(self.timeframe[:-1])
        candles_per_day = 24 * 60 // tf_minutes
        expected_candles = int(self.weeks * 7 * candles_per_day * 0.95)
        
        print(f"🎯 Target: {self.timeframe} candles for {self.weeks} weeks (~{expected_candles:,} candles)")

        all_ohlcv = []
        used_exchange = None

        for ex_name in self.exchanges_to_try:
            print(f"\n🔄 Trying {ex_name.upper()}...")
            try:
                exchange = getattr(ccxt, ex_name)({'enableRateLimit': True})
                since_date = datetime.now(timezone.utc) - timedelta(weeks=self.weeks)
                since = int(since_date.timestamp() * 1000)
                total_fetched = 0

                while True:
                    ohlcv = exchange.fetch_ohlcv(self.symbol, self.timeframe, since, self.limit)
                    if len(ohlcv) == 0:
                        break

                    all_ohlcv.extend(ohlcv)
                    total_fetched += len(ohlcv)

                    since = ohlcv[-1][0] + 60000
                    print(f"  → Fetched {len(ohlcv)} candles | Total: {total_fetched:,}")

                    if len(ohlcv) < self.limit - 50:
                        break

                    time.sleep(0.6)

                # Success check
                if total_fetched >= expected_candles:
                    used_exchange = ex_name
                    print(f"✅ Excellent! Got full history from {ex_name.upper()}")
                    break
                else:
                    all_ohlcv = []
                    print(f"  ⚠️  Only {total_fetched:,} candles — trying next exchange...")

            except Exception as e:
                print(f"  ❌ {ex_name} failed: {e}")
                continue

        if not all_ohlcv:
            print("❌ Not enough data. Try a larger timeframe or let me know!")
            return None

        # Build clean DataFrame
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('datetime').drop(columns=['timestamp'])

        print(f"\n✅ DONE! {len(df):,} {self.timeframe} candles on {used_exchange.upper()}")
        print(f"Period: {df.index[0].date()} → {df.index[-1].date()}")
        print("\nLast 5 rows:")
        print(df.tail())

        # Save
        filename = f"AERO_{self.timeframe}_{self.weeks}weeks_{used_exchange}.csv"
        df.to_csv(filename)
        print(f"\n💾 Saved → {filename}")

        return df


# ========================= CLI + RUN =========================
if __name__ == "__main__":
    # Default = 5m, but accept command-line argument like: python price_3weeks.py 15
    if len(sys.argv) > 1:
        try:
            minutes = int(sys.argv[1])
            timeframe = f"{minutes}m"
            print(f"🛠️  CLI argument detected → using {timeframe} timeframe")
        except ValueError:
            print("⚠️  Invalid argument! Using default 5m (example: python price_3weeks.py 15)")
            timeframe = '5m'
    else:
        timeframe = '5m'

    fetcher = AeroPriceFetcher(timeframe=timeframe)
    fetcher.fetch_and_save()
