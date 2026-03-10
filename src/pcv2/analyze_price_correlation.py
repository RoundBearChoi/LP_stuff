import sys
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import coint, adfuller
import statsmodels.api as sm
import matplotlib.pyplot as plt
from datetime import datetime

def analyze_pair(sym1: str, sym2: str, csv_path: str = "top100_hourly_1year_combined.csv"):
    sym1, sym2 = sym1.upper(), sym2.upper()
    print(f"Analyzing {sym1} vs {sym2}...\n")

    df = pd.read_csv(csv_path)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df[['datetime', 'symbol', 'close']]

    df1 = df[df['symbol'] == sym1].set_index('datetime')[['close']].rename(columns={'close': sym1})
    df2 = df[df['symbol'] == sym2].set_index('datetime')[['close']].rename(columns={'close': sym2})

    data = pd.merge(df1, df2, left_index=True, right_index=True, how='inner').dropna()

    # ==================== NEW UPGRADE: DATE & OVERLAP INFO ====================
    print(f"📅 {sym1} data available from : {df1.index[0].date()}")
    print(f"📅 {sym2} data available from : {df2.index[0].date()}")
    print(f"🔄 Overlap period            : {data.index[0].date()} to {data.index[-1].date()}")
    print(f"   ({len(data):,} hours ≈ {len(data)//24} days)\n")
    
    if len(data) < 4000:
        print("⚠️  WARNING: Short overlap (< ~6 months) — results are still valid but less robust.\n")
    # =========================================================================

    if len(data) < 200:
        print("❌ Not enough overlapping hourly data points.")
        return

    p1 = data[sym1]
    p2 = data[sym2]
    print(f"✅ Overlapping observations: {len(data):,} (from {data.index[0]} to {data.index[-1]})\n")

    # 1. Correlation
    ret1 = np.log(p1).diff().dropna()
    ret2 = np.log(p2).diff().dropna()
    corr = ret1.corr(ret2)
    print(f"📊 Correlation of log returns: {corr:.4f}")

    # 2. Cointegration
    coint_t, coint_p, crit_values = coint(p1, p2, autolag='AIC')
    print(f"🔗 Cointegration p-value: {coint_p:.4f}")
    print(f"   Test statistic: {coint_t:.4f}")

    # 3. Hedge ratio + spread
    X = sm.add_constant(p2)
    model = sm.OLS(p1, X).fit()
    const, beta = model.params
    spread = p1 - beta * p2
    print(f"📏 Hedge ratio (beta): {beta:.4f}  →  long 1 {sym1} : short {beta:.4f} {sym2}")

    # 4. Half-life
    lagged = spread.shift(1).dropna()
    delta = spread.diff().dropna()
    X_ou = sm.add_constant(lagged)
    ou_model = sm.OLS(delta, X_ou).fit()
    kappa = -ou_model.params.iloc[1]
    half_life_hours = np.log(2) / kappa if kappa > 1e-8 else float('inf')
    half_life_days = half_life_hours / 24
    print(f"⏱️  Half-life: {half_life_hours:.1f} hours ≈ {half_life_days:.1f} days")

    # Extra metrics
    adf = adfuller(spread)
    zscore = (spread.iloc[-1] - spread.mean()) / spread.std()
    vol1 = ret1.std() * np.sqrt(24 * 365) * 100
    vol2 = ret2.std() * np.sqrt(24 * 365) * 100

    print(f"📉 ADF p-value on spread: {adf[1]:.4f}")
    print(f"📍 Current spread Z-score: {zscore:.2f}")
    print(f"📈 Annualized volatility: {sym1} = {vol1:.1f}%   |   {sym2} = {vol2:.1f}%")

    # ==================== CHARTS ====================
    filename = f"{sym1}_{sym2}_pairs_analysis.png"
    
    fig, axs = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    fig.suptitle(f'{sym1} vs {sym2} Pairs Analysis\n'
                 f'Corr: {corr:.3f} | Cointegration p: {coint_p:.3f} | Half-life: {half_life_days:.1f} days | '
                 f'Z-score now: {zscore:.2f} | Beta: {beta:.1f}', 
                 fontsize=14, fontweight='bold')

    # 1. Normalized prices
    norm1 = p1 / p1.iloc[0] * 100
    norm2 = p2 / p2.iloc[0] * 100
    axs[0].plot(norm1, label=sym1, linewidth=1.2)
    axs[0].plot(norm2, label=sym2, linewidth=1.2)
    axs[0].set_title('Normalized Prices (both start at 100)')
    axs[0].legend()
    axs[0].grid(True, alpha=0.3)

    # 2. Spread
    axs[1].plot(spread, color='purple', linewidth=1.2)
    axs[1].axhline(spread.mean(), color='black', linestyle='--', linewidth=1)
    axs[1].set_title('Spread (P1 - beta × P2)')
    axs[1].grid(True, alpha=0.3)

    # 3. Z-score
    zseries = (spread - spread.mean()) / spread.std()
    axs[2].plot(zseries, color='red', linewidth=1.2)
    axs[2].axhline(2, color='green', linestyle='--', alpha=0.7, label='+2σ')
    axs[2].axhline(-2, color='green', linestyle='--', alpha=0.7, label='-2σ')
    axs[2].axhline(0, color='black', linestyle='-', alpha=0.5)
    axs[2].set_title('Z-Score of Spread (trading signals at ±2)')
    axs[2].legend()
    axs[2].grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\n📸 Chart saved as: {filename}  (300 DPI - ready for reports or Discord)")

    print("\n" + "="*80)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python analyze_price_correlation.py SOL PUMP")
        sys.exit(1)
    analyze_pair(sys.argv[1], sys.argv[2])
