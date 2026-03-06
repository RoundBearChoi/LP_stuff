import getpass
import os
import pandas as pd
from dune_client.client import DuneClient
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

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
days = min(max(days, 7), 730)  # sane bounds

print(f"Fetching last {days} days of Base DEX data...\n")

# ==================== 3. SQL Query (ad-hoc via Dune API) ====================
# This uses the official dex.trades table + CTEs for clean daily market share
sql = f"""
WITH daily_volumes AS (
    SELECT 
        DATE_TRUNC('day', block_time) AS day,
        project,
        SUM(COALESCE(amount_usd, 0)) AS volume_usd
    FROM dex.trades 
    WHERE blockchain = 'base'
      AND block_time >= NOW() - INTERVAL '{days} days'
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
    dv.day::date AS day,
    dv.project,
    ROUND(dv.volume_usd, 0) AS volume_usd,
    ROUND(td.total_volume, 0) AS total_volume,
    ROUND(100.0 * dv.volume_usd / NULLIF(td.total_volume, 0), 2) AS market_share_pct
FROM daily_volumes dv
JOIN total_daily td ON dv.day = td.day
WHERE dv.volume_usd > 1000  -- filter noise
ORDER BY dv.day DESC, dv.volume_usd DESC;
"""

# ==================== 4. Execute on Dune ====================
dune = DuneClient(api_key=api_key)
print("🚀 Executing query on Dune Analytics (this usually takes 5-20 seconds)...")
results = dune.run_sql(query_sql=sql, performance="medium")  # 'medium' is fast & free-tier friendly

# Convert to pandas DataFrame
df = pd.DataFrame(results.result.rows)
df['day'] = pd.to_datetime(df['day'])

