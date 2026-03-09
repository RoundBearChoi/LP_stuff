import pandas as pd

df = pd.read_csv("btc_daily_1year_coingecko.csv", index_col="timestamp", parse_dates=True)

print("✅ SUCCESS CHECK")
print(f"Rows loaded: {len(df):,}")
print(f"Date range: {df.index[0].date()} → {df.index[-1].date()}")
print(f"Index dtype: {df.index.dtype}")           # ← Should show: datetime64[ns, UTC]
print(f"Timezone: {df.index.tz}")                 # ← Should show: UTC
print(f"First timestamp: {df.index[0]}")          # ← Should end with +00:00
print("\nLast 5 rows (UTC-aware):")
print(df.tail(5))
