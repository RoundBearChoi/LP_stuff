#!/usr/bin/env python3
import pandas as pd
import numpy as np
import argparse
import sys
import warnings
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore")

# ==================== CONFIGURATION SECTION ====================
CONFIG = {
    'n_boots': 5000,                    # Number of stationary bootstrap resamples
    'token0': 'eth',                    # Token 0 (now treated as the "unit" token)
    'token1': 'btc',                    # Token 1 (now the "base" token) → price = token1_USD / token0_USD
    'n_months': 24,                     # How many recent months of history to use
    'horizon_hours': 24*7*2,            # ← SIMULATION HORIZON (24h * 7d * weeks)
    'mean_block_length': 20,            # Mean geometric block length for SB
    'low_percentile': 2.5,              # Lower range percentile
    'high_percentile': 97.5,            # Upper range percentile
    'data_dir': 'fetched_data',         # Folder with the CSVs
    'draw_charts': True,                # ← Set False to skip all visualizations entirely
    'chart_dpi': 180,                   # ← Export DPI (180 is crisp + fast; 300 for print)

    # Lag-1 autocorrelation classification thresholds
    'acf_strong_reversion_threshold': -0.05,   # Values < this → "strong reversion tendency"
    'acf_momentum_threshold':         0.05,    # Values > this → "momentum / trending tendency"
}
# ============================================================

def load_price(token: str) -> pd.Series:
    """Load CSV and convert to KST timezone-aware index."""
    path = f"{CONFIG['data_dir']}/{token}_price_history.csv"
    try:
        df = pd.read_csv(path)
    except FileNotFoundError:
        print(f"❌ ERROR: Could not find {path}")
        sys.exit(1)

    df['datetime'] = pd.to_datetime(df['datetime'], format='ISO8601')
    df = df.set_index('datetime')
    df.index = df.index.tz_convert('Asia/Seoul')   # KST
    return df['price_usd'].sort_index()

def stationary_bootstrap(series: np.ndarray, n: int, mean_block: int) -> np.ndarray:
    T = len(series)
    if T == 0:
        return np.zeros(n)
    p = 1.0 / mean_block
    boot = np.zeros(n)
    idx = 0
    while idx < n:
        start = np.random.randint(0, T)
        L = np.random.geometric(p)
        for k in range(L):
            if idx >= n:
                break
            boot[idx] = series[(start + k) % T]
            idx += 1
    return boot

def main():
    # --- CLI overrides ---
    parser = argparse.ArgumentParser(
        description="Stationary Bootstrap optimal liquidity-pool range (configurable horizon)."
    )
    parser.add_argument('token0', nargs='?', default=None, help='Token 0 (e.g. eth)')
    parser.add_argument('token1', nargs='?', default=None, help='Token 1 (e.g. btc)')
    parser.add_argument('n_months', nargs='?', type=int, default=None, help='Months of history')
    args = parser.parse_args()

    if args.token0 is not None:
        CONFIG['token0'] = args.token0.lower()
    if args.token1 is not None:
        CONFIG['token1'] = args.token1.lower()
    if args.n_months is not None:
        CONFIG['n_months'] = args.n_months

    horizon = CONFIG['horizon_hours']
    horizon_label = f"{horizon}h"
    if horizon == 24:
        horizon_label = "24h (1 day)"
    elif horizon == 168:
        horizon_label = "168h (7 days)"
    elif horizon == 720:
        horizon_label = "720h (30 days)"

    print(f"Running SB for pair {CONFIG['token0'].upper()}-{CONFIG['token1'].upper()} "
          f"({CONFIG['n_months']} months, {horizon_label}, {CONFIG['n_boots']} bootstraps)")

    # --- Load & align data ---
    price0 = load_price(CONFIG['token0'])
    price1 = load_price(CONFIG['token1'])

    combined = pd.DataFrame({
        'price0': price0,
        'price1': price1
    }).sort_index()
    combined = combined.resample('h').last().ffill()

    pair_price = combined['price1'] / combined['price0']

    end_date = pair_price.index.max()
    start_date = end_date - pd.DateOffset(months=CONFIG['n_months'])
    historical = pair_price.loc[start_date:].dropna()

    if len(historical) < 48:
        print("⚠️  WARNING: Less than 2 days of data after filtering — results may be unreliable.")

    # Log returns
    log_returns = np.log(historical).diff().dropna().values

    # Lag-1 autocorrelation (key diagnostic for reversion vs momentum)
    if len(log_returns) > 1:
        lag1_acf = np.corrcoef(log_returns[:-1], log_returns[1:])[0, 1]
    else:
        lag1_acf = 0.0

    # --- Stationary Bootstrap ---
    np.random.seed(42)
    sim_mins = []
    sim_maxs = []

    for _ in range(CONFIG['n_boots']):
        boot_r = stationary_bootstrap(log_returns, n=horizon, mean_block=CONFIG['mean_block_length'])
        path = np.exp(np.cumsum(boot_r))
        path = np.insert(path, 0, 1.0)
        sim_mins.append(path.min())
        sim_maxs.append(path.max())

    # === BOTH RANGES CALCULATED HERE (zero extra runtime cost) ===
    lower_mult = np.percentile(sim_mins, CONFIG['low_percentile'])
    upper_mult = np.percentile(sim_maxs, CONFIG['high_percentile'])

    median_lower = np.median(sim_mins)
    median_upper = np.median(sim_maxs)
    median_dev = np.median([max(1 - m, M - 1) for m, M in zip(sim_mins, sim_maxs)])

    actual_coverage = np.mean(
        (np.array(sim_mins) >= lower_mult) & (np.array(sim_maxs) <= upper_mult)
    ) * 100
    typical_coverage = np.mean(
        (np.array(sim_mins) >= median_lower) & (np.array(sim_maxs) <= median_upper)
    ) * 100

    # --- Console output ---
    print("\n" + "="*80)
    print(f"OPTIMAL LIQUIDITY POOL RANGE for {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()}")
    print("="*80)

    # Autocorrelation diagnostic (emojis stay here only)
    print(f"Lag-1 autocorrelation of log returns : {lag1_acf:.4f} ", end="")
    if lag1_acf < CONFIG['acf_strong_reversion_threshold']:
        print("(🔄 strong reversion tendency)")
    elif lag1_acf < 0:
        print("(🔄 mild reversion tendency)")
    elif lag1_acf > CONFIG['acf_momentum_threshold']:
        print("(📈 momentum / trending tendency)")
    else:
        print("(➡️  near random-walk behaviour)")

    lower_pct = (lower_mult - 1) * 100
    upper_pct = (upper_mult - 1) * 100
    print(f"HIGH-CONFIDENCE COVERAGE (~95% of simulated {horizon_label} paths)")
    print(f"Lower multiplier : {lower_mult:.4f}  →  lower = current × {lower_mult:.4f}  ({lower_pct:+.2f}%)")
    print(f"Upper multiplier : {upper_mult:.4f}  →  upper = current × {upper_mult:.4f}  ({upper_pct:+.2f}%)")
    print(f"Range width      : {(upper_mult / lower_mult - 1)*100:.1f}%")
    print(f"Coverage         : ~{100 - CONFIG['low_percentile']*2:.0f}% of simulated {horizon_label} paths")
    print(f"Actual paths fully covered: {actual_coverage:.1f}% (joint)")

    med_lower_pct = (median_lower - 1) * 100
    med_upper_pct = (median_upper - 1) * 100
    print(f"\nTYPICAL / MAXIMUM-LIKELIHOOD {horizon_label.upper()} RANGE (median, asymmetric)")
    print(f"Lower multiplier : {median_lower:.4f}  →  ({med_lower_pct:+.2f}%)")
    print(f"Upper multiplier : {median_upper:.4f}  →  ({med_upper_pct:+.2f}%)")
    print(f"Range width      : {(median_upper / median_lower - 1)*100:.1f}%")
    print(f"Symmetric ±R     : ±{median_dev*100:.2f}%   (median max-deviation)")
    print(f"Actual paths fully covered: {typical_coverage:.1f}% (joint)")

    print(f"\nBased on         : {len(historical):,} hourly observations")
    print(f"SB parameters    : {CONFIG['n_boots']} bootstraps, mean block = {CONFIG['mean_block_length']}, horizon = {horizon} hours")
    current_price = historical.iloc[-1]
    print(f"Current {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()} price: {current_price:,.4f}")
    print("="*80)

    # ==================== VISUALIZATIONS (conditional) ====================
    if CONFIG['draw_charts']:
        print(f"\nGenerating and exporting charts for {horizon_label} horizon...")

        sns.set_style("darkgrid")
        plt.rcParams['figure.figsize'] = (14, 10)

        fig = plt.figure()

        # 1. Simulated paths (unchanged)
        ax1 = plt.subplot(2, 2, 1)
        np.random.seed(42)
        sample_idx = np.random.choice(len(sim_mins), 200, replace=False)
        for i in sample_idx:
            boot_r = stationary_bootstrap(log_returns, n=horizon, mean_block=CONFIG['mean_block_length'])
            path = np.exp(np.cumsum(boot_r))
            path = np.insert(path, 0, 1.0)
            ax1.plot(range(horizon + 1), path, color='blue', alpha=0.05, lw=1)

        lower_pct = (lower_mult - 1) * 100
        upper_pct = (upper_mult - 1) * 100
        med_lower_pct = (median_lower - 1) * 100
        med_upper_pct = (median_upper - 1) * 100

        ax1.axhline(lower_mult, color='red', linestyle='--', lw=2,
                    label=f'High-conf lower ({lower_mult:.4f} / {lower_pct:+.2f}%)')
        ax1.axhline(upper_mult, color='green', linestyle='--', lw=2,
                    label=f'High-conf upper ({upper_mult:.4f} / {upper_pct:+.2f}%)')
        ax1.axhline(median_lower, color='red', linestyle=':', lw=1.5,
                    label=f'Typical lower ({median_lower:.4f} / {med_lower_pct:+.2f}%)')
        ax1.axhline(median_upper, color='green', linestyle=':', lw=1.5,
                    label=f'Typical upper ({median_upper:.4f} / {med_upper_pct:+.2f}%)')

        offset = 0.0035
        ax1.text(horizon + 0.2, lower_mult + offset, f'  {lower_pct:+.2f}%',
                 color='red', va='bottom', ha='left', fontsize=11, fontweight='bold')
        ax1.text(horizon + 0.2, upper_mult + offset, f'  {upper_pct:+.2f}%',
                 color='green', va='bottom', ha='left', fontsize=11, fontweight='bold')

        ax1.set_title(f'200 Example {horizon_label} Simulated Paths\n(normalized to start = 1.0)')
        ax1.set_xlabel('Hours (KST)')
        ax1.set_ylabel('Price Multiplier')
        ax1.legend(loc='upper left')

        # 2. Histograms (unchanged)
        ax2 = plt.subplot(2, 2, 2)
        sns.histplot(sim_mins, kde=True, color='red', alpha=0.6, label='Simulated Mins', ax=ax2)
        sns.histplot(sim_maxs, kde=True, color='green', alpha=0.6, label='Simulated Maxs', ax=ax2)
        ax2.axvline(lower_mult, color='red', linestyle='--', lw=2, label=f'{CONFIG["low_percentile"]}th %')
        ax2.axvline(upper_mult, color='green', linestyle='--', lw=2, label=f'{CONFIG["high_percentile"]}th %')
        ax2.axvline(median_lower, color='red', linestyle=':', lw=1.5)
        ax2.axvline(median_upper, color='green', linestyle=':', lw=1.5)
        ax2.set_title(f'Distribution of {horizon_label} Extremes')
        ax2.set_xlabel('Multiplier')
        ax2.legend()

        # ← UPDATED: Lag-1 Reversion Visualization
        # Orange ACF box on LEFT, regression line legend on RIGHT
        ax3 = plt.subplot(2, 2, 3)
        n_obs = len(log_returns)
        if n_obs > 1:
            x = log_returns[:-1]
            y = log_returns[1:]
            ax3.scatter(x, y, alpha=0.08, s=4, color='purple')
            if len(x) > 10:
                slope, intercept = np.polyfit(x, y, deg=1)
                x_range = np.linspace(x.min(), x.max(), 100)
                y_fit = slope * x_range + intercept
                ax3.plot(x_range, y_fit, color='red', lw=2.5,
                         label='Regression line')
            ax3.axhline(0, color='gray', linestyle='--', alpha=0.7)
            ax3.axvline(0, color='gray', linestyle='--', alpha=0.7)
            ax3.set_xlabel('log return at t-1')
            ax3.set_ylabel('log return at t')
            ax3.set_title('Lag-1 Reversion Visualization\n(scatter of consecutive hourly log returns)')
            ax3.legend(loc='upper right')   # Regression line label stays on the right

            # Orange ACF box on LEFT (top-left)
            if lag1_acf < CONFIG['acf_strong_reversion_threshold']:
                class_txt = "STRONG REVERSION"
            elif lag1_acf < 0:
                class_txt = "mild reversion"
            elif lag1_acf > CONFIG['acf_momentum_threshold']:
                class_txt = "MOMENTUM"
            else:
                class_txt = "near random-walk"
            ax3.text(0.02, 0.98, f'Lag-1 ACF = {lag1_acf:.4f}\n{class_txt}',
                     transform=ax3.transAxes, fontsize=11,
                     verticalalignment='top', horizontalalignment='left',
                     bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.9))
        else:
            ax3.text(0.5, 0.5, 'Insufficient data for Lag-1 chart', ha='center', va='center')
            ax3.set_title('Lag-1 Reversion')

        # 4. Joint distribution (unchanged)
        ax4 = plt.subplot(2, 2, 4)
        sns.scatterplot(x=sim_mins, y=sim_maxs, alpha=0.15, s=10, color='purple', ax=ax4)
        ax4.axvline(lower_mult, color='red', linestyle='--')
        ax4.axhline(upper_mult, color='green', linestyle='--')
        ax4.axvline(median_lower, color='red', linestyle=':', lw=1.5)
        ax4.axhline(median_upper, color='green', linestyle=':', lw=1.5)
        ax4.set_title(f'Joint (Min, Max) Pairs per {horizon_label} Simulation')
        ax4.set_xlabel('Simulated Minimum Multiplier')
        ax4.set_ylabel('Simulated Maximum Multiplier')

        plt.tight_layout()
        plt.subplots_adjust(top=0.87)

        plt.suptitle(
            f"{CONFIG['token0'].upper()}-{CONFIG['token1'].upper()} SB Ranges\n"
            f"High-confidence (~95%) + Typical (median) + Lag-1 Reversion • {horizon_label} • "
            f"{CONFIG['n_months']} months • {CONFIG['n_boots']} bootstraps",
            fontsize=14, y=0.99
        )

        filename = f"sb_range_{CONFIG['token0']}_{CONFIG['token1']}_{CONFIG['n_months']}m_{horizon}h.png"
        fig.savefig(filename, dpi=CONFIG['chart_dpi'], bbox_inches='tight')
        plt.close(fig)

        print(f"✅ Charts exported as: {filename}  (DPI = {CONFIG['chart_dpi']})")

    else:
        print("\nCharts skipped (draw_charts=False in CONFIG).")

if __name__ == "__main__":
    main()
