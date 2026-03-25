import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ====================== USER PARAMETERS ======================
CSV_PATH = 'top300_hourly_18months_combined.csv'
BACKTEST_MONTHS = 18                              # 18, 12, 6, 24, or None for full dataset

ASSET_A = 'XVG'                                   # ← CHANGE THIS: the asset whose weight we track
ASSET_B = 'BTC'                                   # ← CHANGE THIS: the pairing asset
TARGET_WEIGHT_A = 0.50                            # target allocation to ASSET_A (50/50 classic)

OUTER_BUFFER = 0.05
INNER_REBALANCE_DEV = 0.025
INITIAL_CAPITAL = 2_000.0
FEE_RATE = 0.0000
# ============================================================

# Load the combined hourly dataset
df = pd.read_csv(CSV_PATH)
df['datetime'] = pd.to_datetime(df['datetime'])
df = df.sort_values('datetime').set_index('datetime')

# Optional slice to the most recent N months
if BACKTEST_MONTHS is not None:
    end_dt = df.index.max()
    start_dt = end_dt - pd.DateOffset(months=BACKTEST_MONTHS)
    df = df[df.index >= start_dt]
    print(f"✅ Backtesting only the last {BACKTEST_MONTHS} months: {df.index.min()} → {df.index.max()}")
else:
    print(f"✅ Using full dataset: {df.index.min()} → {df.index.max()}")

# Extract the two assets dynamically
col_a = f'{ASSET_A.lower()}_close'
col_b = f'{ASSET_B.lower()}_close'

a = df[df['symbol'] == ASSET_A][['close']].rename(columns={'close': col_a})
b = df[df['symbol'] == ASSET_B][['close']].rename(columns={'close': col_b})

# Align on exact same timestamps
data = a.join(b, how='inner').dropna()

print(f"Data range after filtering: {data.index[0]} → {data.index[-1]}")
print(f"Total bars: {len(data):,}")

# ====================== BACKTEST ENGINE ======================
portfolio = pd.DataFrame(index=data.index)
portfolio[col_a] = data[col_a]
portfolio[col_b] = data[col_b]

# Initial allocation
price_a_0 = data[col_a].iloc[0]
price_b_0 = data[col_b].iloc[0]
shares_a = (INITIAL_CAPITAL * TARGET_WEIGHT_A) / price_a_0
shares_b = (INITIAL_CAPITAL * (1 - TARGET_WEIGHT_A)) / price_b_0

# Tracking columns
portfolio['a_value'] = np.nan
portfolio['b_value'] = np.nan
portfolio['total_value'] = np.nan
portfolio['weight_a'] = np.nan
portfolio['trade'] = 0.0
portfolio['rebalance'] = False

for ts in portfolio.index:
    a_val = shares_a * portfolio.loc[ts, col_a]
    b_val = shares_b * portfolio.loc[ts, col_b]
    total = a_val + b_val
    
    weight_a = a_val / total if total > 0 else TARGET_WEIGHT_A
    
    portfolio.loc[ts, 'a_value'] = a_val
    portfolio.loc[ts, 'b_value'] = b_val
    portfolio.loc[ts, 'total_value'] = total
    portfolio.loc[ts, 'weight_a'] = weight_a
    
    deviation = weight_a - TARGET_WEIGHT_A
    if abs(deviation) > OUTER_BUFFER:
        new_target = TARGET_WEIGHT_A + np.sign(deviation) * INNER_REBALANCE_DEV
        target_a_val = new_target * total
        target_b_val = (1 - new_target) * total
        trade_usd = abs(target_a_val - a_val)
        fee = trade_usd * FEE_RATE
        trade_usd_net = trade_usd - fee
        
        if target_a_val > a_val:  # buy A, sell B
            shares_a += trade_usd_net / portfolio.loc[ts, col_a]
            shares_b -= trade_usd / portfolio.loc[ts, col_b]
        else:                     # sell A, buy B
            shares_a -= trade_usd / portfolio.loc[ts, col_a]
            shares_b += trade_usd_net / portfolio.loc[ts, col_b]
        
        portfolio.loc[ts, 'trade'] = trade_usd
        portfolio.loc[ts, 'rebalance'] = True
        
        # Recalculate after trade
        a_val = shares_a * portfolio.loc[ts, col_a]
        b_val = shares_b * portfolio.loc[ts, col_b]
        total = a_val + b_val
        portfolio.loc[ts, 'total_value'] = total
        portfolio.loc[ts, 'weight_a'] = a_val / total

# ====================== BENCHMARKS ======================
bh_shares_a = (INITIAL_CAPITAL * TARGET_WEIGHT_A) / data[col_a].iloc[0]
bh_shares_b = (INITIAL_CAPITAL * (1 - TARGET_WEIGHT_A)) / data[col_b].iloc[0]
portfolio['bh_value'] = bh_shares_a * portfolio[col_a] + bh_shares_b * portfolio[col_b]

portfolio['a_only'] = INITIAL_CAPITAL * (portfolio[col_a] / data[col_a].iloc[0])
portfolio['b_only'] = INITIAL_CAPITAL * (portfolio[col_b] / data[col_b].iloc[0])

# ====================== PURCHASING POWER EQUIVALENTS ======================
start_time      = data.index[0]
end_time        = data.index[-1]
start_price_a   = data[col_a].iloc[0]
start_price_b   = data[col_b].iloc[0]
end_price_a     = data[col_a].iloc[-1]
end_price_b     = data[col_b].iloc[-1]

start_a_eq = INITIAL_CAPITAL / start_price_a
start_b_eq = INITIAL_CAPITAL / start_price_b

print(f"\nStarting purchasing power equivalents ({start_time}):")
print(f"  ASSET_A ({ASSET_A}): {start_a_eq:,.4f} {ASSET_A}")
print(f"  ASSET_B ({ASSET_B}): {start_b_eq:,.4f} {ASSET_B}")

final_strategy_value = portfolio['total_value'].iloc[-1]
final_btc_eq = final_strategy_value / end_price_b   # keep "btc" naming for clarity in print
final_a_eq   = final_strategy_value / end_price_a

print(f"\nLatest purchasing power equivalents ({end_time}):")
print(f"  ASSET_A ({ASSET_A}): {final_a_eq:,.2f} {ASSET_A}")
print(f"  ASSET_B ({ASSET_B}): {final_btc_eq:,.4f} {ASSET_B}")

# ====================== PERFORMANCE METRICS ======================
def cagr(series):
    days = (series.index[-1] - series.index[0]).days
    return (series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1

def max_dd(series):
    peak = series.cummax()
    drawdown = (series - peak) / peak
    return drawdown.min()

metrics = pd.DataFrame(index=['Strategy', f'{ASSET_A}_100%', f'{ASSET_B}_100%', 'BuyHold_50/50'])
for col, name in [('total_value', 'Strategy'),
                  ('a_only', f'{ASSET_A}_100%'),
                  ('b_only', f'{ASSET_B}_100%'),
                  ('bh_value', 'BuyHold_50/50')]:
    s = portfolio[col]
    final_val = s.iloc[-1]
    
    final_a_eq = final_val / end_price_a
    final_b_eq = final_val / end_price_b
    
    metrics.loc[name, 'Final Value (USD)'] = final_val
    metrics.loc[name, 'Total Return (%)'] = ((final_val / INITIAL_CAPITAL) - 1) * 100
    metrics.loc[name, 'CAGR (%)'] = cagr(s) * 100
    metrics.loc[name, 'Max DD (%)'] = max_dd(s) * 100
    metrics.loc[name, 'Vol (ann.)'] = s.pct_change().std() * np.sqrt(365.25 * 24) * 100
    metrics.loc[name, 'Sharpe (rf=0)'] = (s.pct_change().mean() / s.pct_change().std()) * np.sqrt(365.25 * 24)
    
    metrics.loc[name, f'Final {ASSET_B} equiv'] = final_b_eq
    metrics.loc[name, f'{ASSET_B} equiv growth (%)'] = ((final_b_eq / start_b_eq) - 1) * 100
    metrics.loc[name, f'Final {ASSET_A} equiv'] = final_a_eq
    metrics.loc[name, f'{ASSET_A} equiv growth (%)'] = ((final_a_eq / start_a_eq) - 1) * 100

print("\n=== BACKTEST RESULTS ===")
print(metrics.round(2))

print(f"\nRebalances triggered: {portfolio['rebalance'].sum():,} "
      f"({portfolio['trade'].sum():,.0f} USD total volume traded)")

# ====================== PLOTS ======================
fig, axs = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[3, 2, 1])

axs[0].plot(portfolio['total_value'], label='Strategy (trigger + partial)', linewidth=2)
axs[0].plot(portfolio['bh_value'], label='Buy-&-Hold 50/50', alpha=0.7)
axs[0].plot(portfolio['a_only'], label=f'100% {ASSET_A}', alpha=0.5)
axs[0].plot(portfolio['b_only'], label=f'100% {ASSET_B}', alpha=0.5)
axs[0].set_title(f'Portfolio Value – Volatility Harvesting Backtest ({ASSET_A}-{ASSET_B})')
axs[0].set_ylabel('USD')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(portfolio['weight_a'], label=f'{ASSET_A} Weight', color='purple')
axs[1].axhline(TARGET_WEIGHT_A, color='black', linestyle='--', label='Target')
axs[1].axhline(TARGET_WEIGHT_A + OUTER_BUFFER, color='red', linestyle=':', label=f'+{OUTER_BUFFER*100}% trigger')
axs[1].axhline(TARGET_WEIGHT_A - OUTER_BUFFER, color='red', linestyle=':')
axs[1].axhline(TARGET_WEIGHT_A + INNER_REBALANCE_DEV, color='orange', linestyle='-.', label=f'±{INNER_REBALANCE_DEV*100}% partial')
axs[1].axhline(TARGET_WEIGHT_A - INNER_REBALANCE_DEV, color='orange', linestyle='-.')
axs[1].set_ylabel(f'{ASSET_A} Weight')
axs[1].legend()
axs[1].grid(True)

rebal_dates = portfolio[portfolio['rebalance']].index
axs[2].vlines(rebal_dates, ymin=0, ymax=portfolio['trade'].max()*1.1 if not portfolio['trade'].empty else 1,
              color='red', alpha=0.6, linewidth=1, label='Rebalance')
axs[2].set_ylabel('Trade Size (USD)')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.savefig('volatility_harvesting_backtest.png', dpi=150, bbox_inches='tight')
plt.close()
print("✅ Chart saved as 'volatility_harvesting_backtest.png' (DPI 150)")
