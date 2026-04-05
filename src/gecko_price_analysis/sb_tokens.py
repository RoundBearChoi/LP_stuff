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
    'mean_block_length': 20,            # Mean geometric block length for SB
    'low_percentile': 2.5,              # Lower range percentile
    'high_percentile': 97.5,            # Upper range percentile
    'data_dir': 'fetched_data',         # Folder with the CSVs
    'draw_charts': True,                # ← Set False to skip all visualizations entirely
    'chart_dpi': 180,                   # ← Export DPI (180 is crisp + fast; 300 for print)
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
        description="Stationary Bootstrap optimal liquidity-pool range (24h KST windows)."
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

    print(f"Running SB for pair {CONFIG['token0'].upper()}-{CONFIG['token1'].upper()} "
          f"({CONFIG['n_months']} months, {CONFIG['n_boots']} bootstraps)")

    # --- Load & align data ---
    price0 = load_price(CONFIG['token0'])   # e.g. ETH
    price1 = load_price(CONFIG['token1'])   # e.g. BTC

    combined = pd.DataFrame({
        'price0': price0,
        'price1': price1
    }).sort_index()
    combined = combined.resample('h').last().ffill()

    # INVERTED: now price = token1_USD / token0_USD  → BTC/ETH = ETH per 1 BTC (~32.4)
    pair_price = combined['price1'] / combined['price0']

    # Use only the most recent n_months
    end_date = pair_price.index.max()
    start_date = end_date - pd.DateOffset(months=CONFIG['n_months'])
    historical = pair_price.loc[start_date:].dropna()

    if len(historical) < 48:
        print("⚠️  WARNING: Less than 2 days of data after filtering — results may be unreliable.")

    # Log returns
    log_returns = np.log(historical).diff().dropna().values

    # --- Stationary Bootstrap ---
    np.random.seed(42)
    sim_mins = []
    sim_maxs = []

    for _ in range(CONFIG['n_boots']):
        boot_r = stationary_bootstrap(log_returns, n=24, mean_block=CONFIG['mean_block_length'])
        path = np.exp(np.cumsum(boot_r))
        path = np.insert(path, 0, 1.0)
        sim_mins.append(path.min())
        sim_maxs.append(path.max())

    # === BOTH RANGES CALCULATED HERE (zero extra runtime cost) ===
    # 1. High-confidence coverage (original 2.5%/97.5% logic)
    lower_mult = np.percentile(sim_mins, CONFIG['low_percentile'])
    upper_mult = np.percentile(sim_maxs, CONFIG['high_percentile'])

    # 2. Typical / maximum-likelihood range (asymmetric median — respects natural skew)
    median_lower = np.median(sim_mins)
    median_upper = np.median(sim_maxs)
    # Symmetric ±R for quick reference (median of the maximum deviation per path)
    median_dev = np.median([max(1 - m, M - 1) for m, M in zip(sim_mins, sim_maxs)])

    # Bonus joint coverage stats
    actual_coverage = np.mean(
        (np.array(sim_mins) >= lower_mult) & (np.array(sim_maxs) <= upper_mult)
    ) * 100
    typical_coverage = np.mean(
        (np.array(sim_mins) >= median_lower) & (np.array(sim_maxs) <= median_upper)
    ) * 100

    # --- Console output with BOTH ranges clearly separated ---
    print("\n" + "="*80)
    print(f"OPTIMAL LIQUIDITY POOL RANGE for {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()}")
    print("="*80)

    # High-confidence block (unchanged meaning, just clearer label)
    lower_pct = (lower_mult - 1) * 100
    upper_pct = (upper_mult - 1) * 100
    print("HIGH-CONFIDENCE COVERAGE (~95% of simulated 24h paths)")
    print(f"Lower multiplier : {lower_mult:.4f}  →  lower = current × {lower_mult:.4f}  ({lower_pct:+.2f}%)")
    print(f"Upper multiplier : {upper_mult:.4f}  →  upper = current × {upper_mult:.4f}  ({upper_pct:+.2f}%)")
    print(f"Range width      : {(upper_mult / lower_mult - 1)*100:.1f}%")
    print(f"Coverage         : ~{100 - CONFIG['low_percentile']*2:.0f}% of simulated 24h paths")
    print(f"Actual paths fully covered: {actual_coverage:.1f}% (joint)")

    # New typical / maximum-likelihood block (asymmetric by design)
    med_lower_pct = (median_lower - 1) * 100
    med_upper_pct = (median_upper - 1) * 100
    print("\nTYPICAL / MAXIMUM-LIKELIHOOD DAILY RANGE (median, asymmetric)")
    print(f"Lower multiplier : {median_lower:.4f}  →  ({med_lower_pct:+.2f}%)")
    print(f"Upper multiplier : {median_upper:.4f}  →  ({med_upper_pct:+.2f}%)")
    print(f"Range width      : {(median_upper / median_lower - 1)*100:.1f}%")
    print(f"Symmetric ±R     : ±{median_dev*100:.2f}%   (median max-deviation)")
    print(f"Actual paths fully covered: {typical_coverage:.1f}% (joint)")

    print(f"\nBased on         : {len(historical):,} hourly observations")
    print(f"SB parameters    : {CONFIG['n_boots']} bootstraps, mean block = {CONFIG['mean_block_length']}")
    current_price = historical.iloc[-1]
    print(f"Current {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()} price: {current_price:,.4f}")
    print("="*80)

    # ==================== VISUALIZATIONS (conditional) ====================
    if CONFIG['draw_charts']:
        print("\nGenerating and exporting charts (no interactive window)...")

        # Style
        sns.set_style("darkgrid")
        plt.rcParams['figure.figsize'] = (14, 10)

        fig = plt.figure()

        # 1. Simulated paths — labels slightly above the lines
        ax1 = plt.subplot(2, 2, 1)
        np.random.seed(42)  # reproducible sample
        sample_idx = np.random.choice(len(sim_mins), 200, replace=False)
        for i in sample_idx:
            boot_r = stationary_bootstrap(log_returns, n=24, mean_block=CONFIG['mean_block_length'])
            path = np.exp(np.cumsum(boot_r))
            path = np.insert(path, 0, 1.0)
            ax1.plot(range(25), path, color='blue', alpha=0.05, lw=1)

        # High-confidence range (solid/dashed as before)
        ax1.axhline(lower_mult, color='red', linestyle='--', lw=2,
                    label=f'High-conf lower ({lower_mult:.4f} / {lower_pct:+.2f}%)')
        ax1.axhline(upper_mult, color='green', linestyle='--', lw=2,
                    label=f'High-conf upper ({upper_mult:.4f} / {upper_pct:+.2f}%)')

        # NEW: Typical/median range (thinner dotted lines — clearly distinguishable)
        ax1.axhline(median_lower, color='red', linestyle=':', lw=1.5,
                    label=f'Typical lower ({median_lower:.4f} / {med_lower_pct:+.2f}%)')
        ax1.axhline(median_upper, color='green', linestyle=':', lw=1.5,
                    label=f'Typical upper ({median_upper:.4f} / {med_upper_pct:+.2f}%)')

        # Labels placed slightly ABOVE the high-confidence lines (unchanged)
        offset = 0.0035
        ax1.text(24.2, lower_mult + offset, f'  {lower_pct:+.2f}%',
                 color='red', va='bottom', ha='left', fontsize=11, fontweight='bold')
        ax1.text(24.2, upper_mult + offset, f'  {upper_pct:+.2f}%',
                 color='green', va='bottom', ha='left', fontsize=11, fontweight='bold')

        ax1.set_title('200 Example 24h Simulated Paths\n(normalized to start = 1.0)')
        ax1.set_xlabel('Hours (KST)')
        ax1.set_ylabel('Price Multiplier')
        ax1.legend(loc='upper left')   # ← legend now shows all 4 lines clearly

        # 2. Histograms of extremes
        ax2 = plt.subplot(2, 2, 2)
        sns.histplot(sim_mins, kde=True, color='red', alpha=0.6, label='Simulated Mins', ax=ax2)
        sns.histplot(sim_maxs, kde=True, color='green', alpha=0.6, label='Simulated Maxs', ax=ax2)
        ax2.axvline(lower_mult, color='red', linestyle='--', lw=2, label=f'{CONFIG["low_percentile"]}th %')
        ax2.axvline(upper_mult, color='green', linestyle='--', lw=2, label=f'{CONFIG["high_percentile"]}th %')
        # NEW: Typical median lines on histogram
        ax2.axvline(median_lower, color='red', linestyle=':', lw=1.5)
        ax2.axvline(median_upper, color='green', linestyle=':', lw=1.5)
        ax2.set_title('Distribution of 24h Extremes')
        ax2.set_xlabel('Multiplier')
        ax2.legend()

        # 3. Ordered rank / quantile plot
        ax3 = plt.subplot(2, 2, 3)
        sorted_mins = np.sort(sim_mins)
        sorted_maxs = np.sort(sim_maxs)
        ranks = np.linspace(0, 100, CONFIG['n_boots'])
        ax3.plot(ranks, sorted_mins, color='red', label='Ordered sim_mins')
        ax3.plot(ranks, sorted_maxs, color='green', label='Ordered sim_maxs')
        ax3.axhline(lower_mult, color='red', linestyle=':', lw=1.5)
        ax3.axhline(upper_mult, color='green', linestyle=':', lw=1.5)
        ax3.axvline(CONFIG['low_percentile'], color='gray', linestyle='--', alpha=0.7)
        ax3.axvline(CONFIG['high_percentile'], color='gray', linestyle='--', alpha=0.7)
        ax3.set_title('Ordered Rank / Empirical Quantile Plot')
        ax3.set_xlabel('Percentile Rank (%)')
        ax3.set_ylabel('Multiplier')
        ax3.legend()

        # 4. Joint distribution
        ax4 = plt.subplot(2, 2, 4)
        sns.scatterplot(x=sim_mins, y=sim_maxs, alpha=0.15, s=10, color='purple', ax=ax4)
        ax4.axvline(lower_mult, color='red', linestyle='--')
        ax4.axhline(upper_mult, color='green', linestyle='--')
        # NEW: Typical median lines on joint scatter
        ax4.axvline(median_lower, color='red', linestyle=':', lw=1.5)
        ax4.axhline(median_upper, color='green', linestyle=':', lw=1.5)
        ax4.set_title('Joint (Min, Max) Pairs per Simulation')
        ax4.set_xlabel('Simulated Minimum Multiplier')
        ax4.set_ylabel('Simulated Maximum Multiplier')

        # FINAL LAYOUT
        plt.tight_layout()
        plt.subplots_adjust(top=0.87)

        plt.suptitle(
            f"{CONFIG['token0'].upper()}-{CONFIG['token1'].upper()} SB Ranges\n"
            f"High-confidence (~95%) + Typical (median) • "
            f"{CONFIG['n_months']} months • {CONFIG['n_boots']} bootstraps",
            fontsize=14, y=0.99
        )

        # EXPORT ONLY
        filename = f"sb_range_{CONFIG['token0']}_{CONFIG['token1']}_{CONFIG['n_months']}m.png"
        fig.savefig(filename, dpi=CONFIG['chart_dpi'], bbox_inches='tight')
        plt.close(fig)

        print(f"✅ Charts exported as: {filename}  (DPI = {CONFIG['chart_dpi']})")

    else:
        print("\nCharts skipped (draw_charts=False in CONFIG).")

if __name__ == "__main__":
    main()
