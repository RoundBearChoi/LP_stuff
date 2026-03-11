import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import adfuller
import os

# =============================================
# Cointegration chart — NOW WITH ROLLING PANEL (5 charts total)
# Default CSV: top100_hourly_1year_combined.csv
# Usage: python draw_cointegration_chart.py ETH BTC
# =============================================

DEFAULT_CSV = "top100_hourly_1year_combined.csv"

# Argument handling
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

# Pair-specific full history (no other coins limiting the range)
df = pd.read_csv(csv_file, parse_dates=['datetime'])
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

# Full-sample model
X = add_constant(log_p2)
model = OLS(log_p1, X).fit()
beta = model.params.iloc[1]
spread = log_p1 - beta * log_p2
zscore = (spread - spread.mean()) / spread.std()
adf = adfuller(spread, maxlag=1, regression='c')
p_value = adf[1]

# Dynamic full-sample verdict (unchanged)
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

print("\n=== FULL-SAMPLE RESULTS ===")
print(f"Hedge ratio (beta): {beta:.4f}")
print(f"ADF p-value: {p_value:.6f} → {verdict}")

# Ratio for chart 2
ratio = p1 / p2
ratio_rolling_mean = ratio.rolling(window=720, min_periods=1).mean()
ratio_rolling_std = ratio.rolling(window=720, min_periods=1).std()

# ====================== ROLLING COINTEGRATION (90-day windows) ======================
print("\nComputing rolling cointegration (90-day windows, updated daily)...")
window_days = 90                    # ← CHANGE THIS IF YOU WANT (e.g. 60 or 180)
window = window_days * 24
step = 24                           # daily step for speed + smooth chart

rolling_dates = []
rolling_betas = []
rolling_pvals = []

for i in range(0, len(log_p1) - window + 1, step):
    log_p1_win = log_p1.iloc[i:i+window]
    log_p2_win = log_p2.iloc[i:i+window]
    
    X_win = add_constant(log_p2_win)
    model_win = OLS(log_p1_win, X_win).fit()
    beta_win = model_win.params.iloc[1]
    
    spread_win = log_p1_win - beta_win * log_p2_win
    adf_win = adfuller(spread_win, maxlag=1, regression='c')
    p_win = adf_win[1]
    
    rolling_betas.append(beta_win)
    rolling_pvals.append(p_win)
    rolling_dates.append(log_p1.index[i + window - 1])  # end-of-window date

print(f"Rolling windows computed: {len(rolling_dates)}")

# ====================== 5 CHARTS VERTICALLY ======================
fig, axs = plt.subplots(5, 1, figsize=(14, 23), sharex=True, gridspec_kw={'hspace': 0.35})

# Chart 1–4 (unchanged)
norm1 = p1 / p1.iloc[0] * 100
norm2 = p2 / p2.iloc[0] * 100
axs[0].plot(norm1.index, norm1, label=sym1, linewidth=2)
axs[0].plot(norm2.index, norm2, label=sym2, linewidth=2)
axs[0].set_title(f"1. Normalized Prices — {sym1} vs {sym2}")
axs[0].legend()
axs[0].grid(True, alpha=0.3)

axs[1].plot(ratio.index, ratio, label=f"{sym1}/{sym2} Ratio", color='purple', linewidth=2)
axs[1].plot(ratio_rolling_mean.index, ratio_rolling_mean, label='~30-day Rolling Mean', color='orange', linewidth=2)
axs[1].fill_between(ratio.index, ratio_rolling_mean - 2*ratio_rolling_std, 
                    ratio_rolling_mean + 2*ratio_rolling_std, color='orange', alpha=0.15)
axs[1].set_title("2. Price Ratio")
axs[1].legend()
axs[1].grid(True, alpha=0.3)

axs[2].plot(spread.index, spread, label='Spread', color='blue', linewidth=2)
axs[2].axhline(spread.mean(), color='red', linestyle='--', label='Mean')
axs[2].fill_between(spread.index, spread.mean()-2*spread.std(), spread.mean()+2*spread.std(),
                    color='red', alpha=0.15)
axs[2].set_title(f"3. Spread = log({sym1}) − {beta:.4f} × log({sym2})")
axs[2].legend()
axs[2].grid(True, alpha=0.3)

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

# ====================== NEW CHART 5: ROLLING COINTEGRATION ======================
ax_beta = axs[4]
ax_p = ax_beta.twinx()

ax_beta.plot(rolling_dates, rolling_betas, color='blue', linewidth=2, label='Rolling Beta (hedge ratio)')
ax_p.plot(rolling_dates, rolling_pvals, color='red', linewidth=2, label='Rolling ADF p-value')

# Green shading where cointegrated (p < 0.05)
pvals_arr = np.array(rolling_pvals)
dates_arr = pd.to_datetime(rolling_dates)
mask = pvals_arr < 0.05
ax_p.fill_between(dates_arr, 0, 0.05, where=mask, color='lightgreen', alpha=0.4, label='Cointegrated window (p<0.05)')

ax_p.axhline(0.01, color='darkgreen', linestyle='--', alpha=0.7)
ax_p.axhline(0.05, color='green', linestyle='--', linewidth=2, label='p=0.05 threshold')
ax_p.axhline(0.10, color='orange', linestyle='--', alpha=0.7)

ax_beta.set_ylabel('Rolling Beta', color='blue')
ax_p.set_ylabel('Rolling ADF p-value', color='red')
ax_beta.set_title(f"5. Rolling Cointegration (90-day windows) — Beta & ADF p-value")
ax_beta.grid(True, alpha=0.3)

# Combined legend
lines1, labels1 = ax_beta.get_legend_handles_labels()
lines2, labels2 = ax_p.get_legend_handles_labels()
ax_beta.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

# Dynamic highlight box (still shows full-sample verdict)
fig.text(0.5, 0.935, 
         f"FULL-SAMPLE: ADF p-value = {p_value:.5f}\n"
         f"Beta = {beta:.4f}\n"
         f"{verdict}",
         fontsize=15, ha='center', va='center', fontweight='bold',
         bbox=dict(boxstyle="round,pad=1", facecolor=box_color, alpha=0.9, edgecolor='black'))

fig.suptitle(f"COINTEGRATION ANALYSIS: {sym1} vs {sym2} — {len(p1):,} hourly bars "
             f"({p1.index[0].date()} to {p1.index[-1].date()})", 
             fontsize=16, y=0.98)

plt.tight_layout(rect=[0, 0, 1, 0.91])
output_file = f"cointegration_{sym1}_{sym2}_with_rolling.png"
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\n✅ Saved: {output_file} (now with 5 charts + rolling panel!)")
plt.show()
