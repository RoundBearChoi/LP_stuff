#!/usr/bin/env python3
import pandas as pd
import numpy as np
import argparse
import sys
import warnings

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

    # --- Optimal range ---
    lower_mult = np.percentile(sim_mins, CONFIG['low_percentile'])
    upper_mult = np.percentile(sim_maxs, CONFIG['high_percentile'])

    print("\n" + "="*80)
    print(f"OPTIMAL LIQUIDITY POOL RANGE for {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()}")
    print("="*80)
    print(f"Lower multiplier : {lower_mult:.4f}  →  lower = current × {lower_mult:.4f}")
    print(f"Upper multiplier : {upper_mult:.4f}  →  upper = current × {upper_mult:.4f}")
    print(f"Range width      : {(upper_mult / lower_mult - 1)*100:.1f}%")
    print(f"Coverage         : ~{100 - CONFIG['low_percentile']*2:.0f}% of simulated 24h paths")
    print(f"Based on         : {len(historical):,} hourly observations")
    print(f"SB parameters    : {CONFIG['n_boots']} bootstraps, mean block = {CONFIG['mean_block_length']}")
    print("="*80)

    current_price = historical.iloc[-1]
    print(f"Current {CONFIG['token0'].upper()} per {CONFIG['token1'].upper()} price: {current_price:,.4f}")

if __name__ == "__main__":
    main()
