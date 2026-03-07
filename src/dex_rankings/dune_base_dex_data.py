import getpass
import os
import pandas as pd
from dune_client.client import DuneClient

print("=== Base DEX Historic Data Fetcher (Top 5 Market Share) ===\n")

# ==================== 1. Get API Key ====================
api_key = os.getenv("DUNE_API_KEY")
if not api_key:
    api_key = getpass.getpass("Enter your Dune Analytics API key: ").strip()
    if not api_key:
        print("❌ API key required. Exiting.")
        exit()

# ==================== 2. User inputs ====================
try:
    days = int(input("How many days of historic data? (default 180, max ~730): ") or "180")
except ValueError:
    days = 180
days = min(max(days, 7), 730)

print(f"Fetching last {days} days of Base DEX data...\n")

# ==================== 3. FIXED SQL Query (100% Trino-compatible) ====================
sql = f"""
WITH daily_volumes AS (
    SELECT 
        CAST(DATE_TRUNC('day', block_time) AS DATE) AS day,
        project,
        SUM(COALESCE(amount_usd, 0)) AS volume_usd
    FROM dex.trades 
    WHERE blockchain = 'base'
      AND block_time >= CURRENT_TIMESTAMP - INTERVAL '{days}' DAY   -- ← THIS WAS THE FIX
    GROUP BY 1, 2
),
total_daily AS (
    SELECT 
        day,
        SUM(volume_usd) AS total_volume
    FROM daily_volumes 
    GROUP BY day
)
SELECT 
    dv.day,
    dv.project,
    ROUND(dv.volume_usd, 0) AS volume_usd,
    ROUND(td.total_volume, 0) AS total_volume,
    ROUND(100.0 * dv.volume_usd / NULLIF(td.total_volume, 0), 2) AS market_share_pct
FROM daily_volumes dv
JOIN total_daily td ON dv.day = td.day
WHERE dv.volume_usd > 1000
ORDER BY dv.day DESC, dv.volume_usd DESC;
"""

# ==================== 4. Execute on Dune ====================
dune = DuneClient(api_key=api_key)
print("🚀 Executing query on Dune Analytics (usually 5-20 seconds)...")

results = dune.run_sql(query_sql=sql, performance="medium")

# Convert to pandas DataFrame
df = pd.DataFrame(results.result.rows)
df['day'] = pd.to_datetime(df['day']).dt.date

# ==================== 5. Success output & quick preview ====================
print(f"\n✅ SUCCESS! Fetched {len(df):,} rows ({days} days of data).")
print("\nPreview (most recent day first):")
print(df.head(10).to_string(index=False))

# Latest day summary
latest = df[df['day'] == df['day'].max()]
print("\n=== Top projects on the most recent day ===")
print(latest[['project', 'volume_usd', 'market_share_pct']].head(10).to_string(index=False))

# Optional: save to CSV
df.to_csv(f"base_dex_{days}d.csv", index=False)
print(f"\n💾 Saved to base_dex_{days}d.csv")
