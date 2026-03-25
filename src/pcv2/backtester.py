import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# ====================== USER PARAMETERS ======================
CSV_PATH = 'top300_hourly_18months_combined.csv'  # change if your full file has a different name
TARGET_WEIGHT_XVG = 0.50          # 50/50 is the classic harvesting target
OUTER_BUFFER = 0.05               # 5% trigger
INNER_REBALANCE_DEV = 0.025       # rebalance only to ±2.5% (your 2-3% suggestion)
INITIAL_CAPITAL = 2_000.0        # USD
FEE_RATE = 0.0000                 # set to 0.001 (0.1%) for realism
# ============================================================

# Load the combined hourly dataset
df = pd.read_csv(CSV_PATH)
df['datetime'] = pd.to_datetime(df['datetime'])
df = df.sort_values('datetime').set_index('datetime')

# Extract XVG and BTC (assumes prices are in the same quote currency, usually USD/USDT)
xvg = df[df['symbol'] == 'XVG'][['close']].rename(columns={'close': 'xvg_close'})
btc = df[df['symbol'] == 'BTC'][['close']].rename(columns={'close': 'btc_close'})

# Align on exact same timestamps (inner join – only hours where both exist)
data = xvg.join(btc, how='inner').dropna()

print(f"Data range: {data.index[0]} → {data.index[-1]}")
print(f"Total bars: {len(data):,}")

# ====================== BACKTEST ENGINE ======================
portfolio = pd.DataFrame(index=data.index)
portfolio['xvg_close'] = data['xvg_close']
portfolio['btc_close'] = data['btc_close']

# Initial allocation
xvg_price_0 = data['xvg_close'].iloc[0]
btc_price_0 = data['btc_close'].iloc[0]
xvg_shares = (INITIAL_CAPITAL * TARGET_WEIGHT_XVG) / xvg_price_0
btc_shares = (INITIAL_CAPITAL * (1 - TARGET_WEIGHT_XVG)) / btc_price_0

# Tracking columns
portfolio['xvg_value'] = np.nan
portfolio['btc_value'] = np.nan
portfolio['total_value'] = np.nan
portfolio['xvg_weight'] = np.nan
portfolio['trade'] = 0.0          # USD traded (absolute)
portfolio['rebalance'] = False

trades = []

for i, ts in enumerate(portfolio.index):
    xvg_val = xvg_shares * portfolio.loc[ts, 'xvg_close']
    btc_val = btc_shares * portfolio.loc[ts, 'btc_close']
    total = xvg_val + btc_val
    
    weight_xvg = xvg_val / total if total > 0 else TARGET_WEIGHT_XVG
    
    portfolio.loc[ts, 'xvg_value'] = xvg_val
    portfolio.loc[ts, 'btc_value'] = btc_val
    portfolio.loc[ts, 'total_value'] = total
    portfolio.loc[ts, 'xvg_weight'] = weight_xvg
    
    # Trigger check
    deviation = weight_xvg - TARGET_WEIGHT_XVG
    if abs(deviation) > OUTER_BUFFER:
        # Partial rebalance: move only to INNER_REBALANCE_DEV on the same side
        new_target_weight = TARGET_WEIGHT_XVG + np.sign(deviation) * INNER_REBALANCE_DEV
        
        # Target values at new weight
        target_xvg_val = new_target_weight * total
        target_btc_val = (1 - new_target_weight) * total
        
        # How much to trade (USD)
        trade_usd = abs(target_xvg_val - xvg_val)
        
        # Apply fees
        fee = trade_usd * FEE_RATE
        trade_usd_net = trade_usd - fee
        
        # Execute trade
        if target_xvg_val > xvg_val:  # buy XVG, sell BTC
            xvg_shares += trade_usd_net / portfolio.loc[ts, 'xvg_close']
            btc_shares -= trade_usd / portfolio.loc[ts, 'btc_close']
        else:                         # sell XVG, buy BTC
            xvg_shares -= trade_usd / portfolio.loc[ts, 'xvg_close']
            btc_shares += trade_usd_net / portfolio.loc[ts, 'btc_close']
        
        portfolio.loc[ts, 'trade'] = trade_usd
        portfolio.loc[ts, 'rebalance'] = True
        trades.append((ts, weight_xvg, new_target_weight, trade_usd))
        
        # Recalculate values after trade (for logging only)
        xvg_val = xvg_shares * portfolio.loc[ts, 'xvg_close']
        btc_val = btc_shares * portfolio.loc[ts, 'btc_close']
        total = xvg_val + btc_val
        portfolio.loc[ts, 'total_value'] = total
        portfolio.loc[ts, 'xvg_weight'] = xvg_val / total

# ====================== BENCHMARKS ======================
# Buy-and-hold 50/50 (never rebalances)
bh_xvg_shares = (INITIAL_CAPITAL * TARGET_WEIGHT_XVG) / data['xvg_close'].iloc[0]
bh_btc_shares = (INITIAL_CAPITAL * (1 - TARGET_WEIGHT_XVG)) / data['btc_close'].iloc[0]
portfolio['bh_value'] = bh_xvg_shares * portfolio['xvg_close'] + bh_btc_shares * portfolio['btc_close']

# 100% XVG
portfolio['xvg_only'] = INITIAL_CAPITAL * (portfolio['xvg_close'] / data['xvg_close'].iloc[0])

# 100% BTC
portfolio['btc_only'] = INITIAL_CAPITAL * (portfolio['btc_close'] / data['btc_close'].iloc[0])

# ====================== PERFORMANCE METRICS ======================
def cagr(series):
    days = (series.index[-1] - series.index[0]).days
    return (series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1

def max_dd(series):
    peak = series.cummax()
    drawdown = (series - peak) / peak
    return drawdown.min()

metrics = pd.DataFrame(index=['Strategy', 'BuyHold_50/50', 'XVG_100%', 'BTC_100%'])
for col, name in [('total_value', 'Strategy'),
                  ('bh_value', 'BuyHold_50/50'),
                  ('xvg_only', 'XVG_100%'),
                  ('btc_only', 'BTC_100%')]:
    s = portfolio[col]
    metrics.loc[name, 'Final Value'] = s.iloc[-1]
    metrics.loc[name, 'CAGR'] = cagr(s) * 100
    metrics.loc[name, 'Max DD'] = max_dd(s) * 100
    metrics.loc[name, 'Vol (ann.)'] = s.pct_change().std() * np.sqrt(365.25 * 24) * 100  # hourly → annual
    metrics.loc[name, 'Sharpe (rf=0)'] = (s.pct_change().mean() / s.pct_change().std()) * np.sqrt(365.25 * 24)

print("\n=== BACKTEST RESULTS ===")
print(metrics.round(2))

print(f"\nRebalances triggered: {portfolio['rebalance'].sum():,} "
      f"({portfolio['trade'].sum():,.0f} USD total volume traded)")

# ====================== PLOTS ======================
fig, axs = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[3, 2, 1])

# Equity curves
axs[0].plot(portfolio['total_value'], label='Strategy (trigger + partial)', linewidth=2)
axs[0].plot(portfolio['bh_value'], label='Buy-&-Hold 50/50', alpha=0.7)
axs[0].plot(portfolio['xvg_only'], label='100% XVG', alpha=0.5)
axs[0].plot(portfolio['btc_only'], label='100% BTC', alpha=0.5)
axs[0].set_title('Portfolio Value – Volatility Harvesting Backtest (XVG-BTC)')
axs[0].set_ylabel('USD')
axs[0].legend()
axs[0].grid(True)

# XVG weight evolution
axs[1].plot(portfolio['xvg_weight'], label='XVG Weight', color='purple')
axs[1].axhline(TARGET_WEIGHT_XVG, color='black', linestyle='--', label='Target')
axs[1].axhline(TARGET_WEIGHT_XVG + OUTER_BUFFER, color='red', linestyle=':', label=f'+{OUTER_BUFFER*100}% trigger')
axs[1].axhline(TARGET_WEIGHT_XVG - OUTER_BUFFER, color='red', linestyle=':')
axs[1].axhline(TARGET_WEIGHT_XVG + INNER_REBALANCE_DEV, color='orange', linestyle='-.', label=f'±{INNER_REBALANCE_DEV*100}% partial')
axs[1].axhline(TARGET_WEIGHT_XVG - INNER_REBALANCE_DEV, color='orange', linestyle='-.')
axs[1].set_ylabel('XVG Weight')
axs[1].legend()
axs[1].grid(True)

# Trade markers
rebal_dates = portfolio[portfolio['rebalance']].index
axs[2].vlines(rebal_dates, ymin=0, ymax=portfolio['trade'].max()*1.1,
              color='red', alpha=0.6, linewidth=1, label='Rebalance')
axs[2].set_ylabel('Trade Size (USD)')
axs[2].legend()
axs[2].grid(True)

plt.tight_layout()
plt.show()
