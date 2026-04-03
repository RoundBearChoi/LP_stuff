# === FULL UPDATED volatility_check.py (copy-paste this entire file) ===
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Load from the fetched_data directory
btc_df = pd.read_csv('fetched_data/btc_price_history.csv')
eth_df = pd.read_csv('fetched_data/eth_price_history.csv')

# Parse datetimes
btc_df['datetime'] = pd.to_datetime(btc_df['datetime'], format='mixed', utc=True)
eth_df['datetime'] = pd.to_datetime(eth_df['datetime'], format='mixed', utc=True)

btc = btc_df.set_index('datetime').rename(columns={'price_usd': 'btc'}).sort_index()
eth = eth_df.set_index('datetime').rename(columns={'price_usd': 'eth'}).sort_index()

# Align prices
combined = pd.merge_asof(
    btc, eth,
    left_index=True,
    right_index=True,
    direction='nearest',
    tolerance=pd.Timedelta('30min')
)
combined = combined.dropna()

# Convert to KST + compute ratio volatility
combined.index = combined.index.tz_convert('Asia/Seoul')
combined['ratio'] = combined['eth'] / combined['btc']
combined['log_ret'] = np.log(combined['ratio']).diff()
combined['hour'] = combined.index.hour

# === RESULTS (same as before) ===
vol = combined.groupby('hour')['log_ret'].std().sort_values()
print("Volatility (std of log returns) by KST hour (lowest → highest):\n", vol)

stats = combined.groupby('hour')['log_ret'].agg(
    mean='mean', std='std', count='count', min='min', max='max'
).sort_values('std')
print("\nFull stats table (sorted by lowest volatility):\n", stats)

# === CHART: exported to PNG only (no interactive window) ===
plt.figure(figsize=(14, 8))

# Bar chart for volatility (std)
bars = plt.bar(vol.index, vol.values, color='skyblue', edgecolor='navy', alpha=0.85, linewidth=1.2)

# Highlight the 3 calmest hours in gold
calmest_hours = vol.head(3).index.tolist()
for hour in calmest_hours:
    idx = list(vol.index).index(hour)
    bars[idx].set_color('gold')
    bars[idx].set_edgecolor('darkorange')
    bars[idx].set_linewidth(2)

plt.title('ETH/BTC Price Ratio Volatility by Hour (KST)\nLower bar = calmer hour for the ratio (least chop)', 
          fontsize=16, fontweight='bold', pad=20)
plt.xlabel('Hour of Day in KST (0 = midnight, 23 = 11 PM)', fontsize=13)
plt.ylabel('Volatility (Standard Deviation of Log Returns)', fontsize=13)
plt.xticks(range(0, 24), fontsize=11)
plt.yticks(fontsize=11)
plt.grid(axis='y', linestyle='--', alpha=0.4)

# Add exact volatility values on top of every bar
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height + 0.00005,
             f'{height:.5f}', ha='center', va='bottom', fontsize=9, rotation=90)

# Optional: small annotation for the calmest window
plt.axvspan(13.5, 20.5, alpha=0.1, color='green', label='Afternoon–Evening calm window (2–8 PM KST)')
plt.legend(loc='upper right')

plt.tight_layout()
plt.savefig('eth_btc_kst_volatility.png', dpi=150, bbox_inches='tight')

print("\n✅ Chart exported as 'eth_btc_kst_volatility.png' (DPI 150) in your current folder!")
