import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import adfuller
import os

# =============================================
# Cointegration chart — FIXED data loading for full pair history
# Now shows true 1-year range for any pair (not limited by other coins)
# Usage: python draw_cointegration_chart.py ETH BTC
# =============================================

DEFAULT_CSV = "top100_hourly_1year_combined.csv"

if len(sys.argv) == 4:
    csv_file = sys.argv[1]
    sym1 = sys.argv[2].upper()
    sym2 = sys.argv[3].upper()
elif len(sys.argv) == 3:
    csv_file = DEFAULT_CSV
    sym1 = sys.argv[1].upper()
    sym2 = sys.argv[2].upper()
else:
    print(f"Usage: python {sys.argv[0]} ETH BTC")
    sys.exit(1)

print(f"Loading {csv_file} → analyzing {sym1} vs {sym2}")

if not os.path.exists(csv_file):
    print(f"❌ File '{csv_file}' not found!")
    sys.exit(1)

# ====================== FIXED DATA LOADING ======================
df = pd.read_csv(csv_file, parse_dates=['datetime'])

# NEW: select ONLY the two symbols FIRST → full overlapping history
df_pair = df[df['symbol'].isin([sym1, sym2])].copy()
pivot = df_pair.pivot(index='datetime', columns='symbol', values='close').dropna()

if sym1 not in pivot.columns or sym2 not in pivot.columns:
    print(f"❌ Symbols not found. Available: {list(pivot.columns)}")
    sys.exit(1)

p1 = pivot[sym1]
p2 = pivot[sym2]

print(f"Data range for {sym1}/{sym2}: {p1.index[0].date()} → {p1.index[-1].date()} ({len(p1):,} hourly rows)")

log_p1 = np.log(p1)
log_p2 = np.log(p2)

X = add_constant(log_p2)
model = OLS(log_p1, X).fit()
beta = model.params.iloc[1]
spread = log_p1 - beta * log_p2

zscore = (spread - spread.mean()) / spread.std()

adf = adfuller(spread, maxlag=1, regression='c')
p_value = adf[1]

# Dynamic verdict (same as last version)
if p_value < 0.01:
    verdict = f"✅ STRONG COINTEGRATION (p < 0.01)"
    box_color = 'lime'
elif p_value < 0.05:
    verdict = f"✅ MODERATE COINTEGRATION (p < 0.05)"
    box_color = 'lightgreen'
elif p_value < 0.10:
    verdict = f"⚠️ WEAK / MARGINAL (p < 0.10)"
    box_color = 'yellow'
else:
    verdict = f"❌ NO COINTEGRATION (p ≥ 0.10)"
    box_color = 'salmon'

print("\n=== COINTEGRATION RESULTS ===")
print(f"Hedge ratio (beta): {beta:.4f}")
print(f"ADF p-value: {p_value:.6f} → {verdict}")

# Rolling stats (~30 days)
ratio = p1 / p2
ratio_rolling_mean = ratio.rolling(window=720, min_periods=1).mean()
ratio_rolling_std = ratio.rolling(window=720, min_periods=1).std()

# ====================== PLOTS (unchanged) ======================
fig, axs = plt.subplots(4, 1, figsize=(14, 19), sharex=True, gridspec_kw={'hspace': 0.35})

# Chart 1
norm1 = p1 / p1.iloc[0] * 100
norm2 = p2 / p2.iloc[0] * 100
axs[0].plot(norm1.index, norm1, label=sym1, linewidth=2)
axs[0].plot(norm2.index, norm2, label=sym2, linewidth=2)
axs[0].set_title(f"1. Normalized Prices — {sym1} vs {sym2}")
axs[0].legend()
axs[0].grid(True, alpha=0.3)

# Chart 2
axs[1].plot(ratio.index, ratio, label=f"{sym1}/{sym2} Ratio", color='purple', linewidth=2)
axs[1].plot(ratio_rolling_mean.index, ratio_rolling_mean, label='~30-day Rolling Mean', color='orange', linewidth=2)
axs[1].fill_between(ratio.index, ratio_rolling_mean - 2*ratio_rolling_std, 
                    ratio_rolling_mean + 2*ratio_rolling_std, color='orange', alpha=0.15)
axs[1].set_title("2. Price Ratio")
axs[1].legend()
axs[1].grid(True, alpha=0.3)

# Chart 3
axs[2].plot(spread.index, spread, label='Spread', color='blue', linewidth=2)
axs[2].axhline(spread.mean(), color='red', linestyle='--', label='Mean')
axs[2].fill_between(spread.index, spread.mean()-2*spread.std(), spread.mean()+2*spread.std(),
                    color='red', alpha=0.15)
axs[2].set_title(f"3. Spread = log({sym1}) − {beta:.4f} × log({sym2})")
axs[2].legend()
axs[2].grid(True, alpha=0.3)

# Chart 4
axs[3].plot(zscore.index, zscore, label='Z-Score', color='darkgreen', linewidth=2)
axs[3].axhline(0, color='black', linestyle='--')
axs[3].axhline(2, color='red', linestyle='--', label='+2/-2 Entry')
axs[3].axhline(-2, color='red', linestyle='--')
axs[3].axhline(1, color='orange', linestyle='--', label='+1/-1 Exit')
axs[3].axhline(-1, color='orange', linestyle='--')
axs[3].set_title("4. Z-Score of Spread")
axs[3].legend()
axs[3].grid(True, alpha=0.3)
axs[3].set_ylim(-5, 5)

# Dynamic highlight box
fig.text(0.5, 0.935, 
         f"ADF p-value = {p_value:.5f}\n"
         f"Beta (hedge ratio) = {beta:.4f}\n"
         f"{verdict}",
         fontsize=15, ha='center', va='center', fontweight='bold',
         bbox=dict(boxstyle="round,pad=1", facecolor=box_color, alpha=0.9, edgecolor='black'))

fig.suptitle(f"COINTEGRATION ANALYSIS: {sym1} vs {sym2} — {len(p1):,} hourly bars "
             f"({p1.index[0].date()} to {p1.index[-1].date()})", 
             fontsize=16, y=0.98)

plt.tight_layout(rect=[0, 0, 1, 0.91])
output_file = f"cointegration_{sym1}_{sym2}.png"
plt.savefig(output_file, dpi=200, bbox_inches='tight')
print(f"\n✅ Saved: {output_file} (now with full pair history!)")
plt.show()
