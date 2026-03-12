import pandas as pd
import numpy as np
import sys
import warnings
from pathlib import Path
from datetime import timedelta

# Silence the pandas concat FutureWarning permanently
warnings.filterwarnings("ignore", message="Sorting by default when concatenating all DatetimeIndex")

def main():
    if len(sys.argv) < 3:
        print("Usage: python get_correlation.py <symbol1> <symbol2> [csv_file]")
        print("Example: python get_correlation.py pump sol")
        sys.exit(1)

    sym1 = sys.argv[1].upper()
    sym2 = sys.argv[2].upper()
    file_path = sys.argv[3] if len(sys.argv) > 3 else "top100_hourly_1year_combined.csv"

    if not Path(file_path).exists():
        print(f"Error: File '{file_path}' not found.")
        sys.exit(1)

    print(f"Loading {file_path} and computing {sym1} vs {sym2} correlation...")

    df = pd.read_csv(file_path)
    print(f"Loaded {len(df):,} rows. Columns detected: {df.columns.tolist()}")

    # Auto-detect time column (works with your 'datetime')
    time_candidates = ['time', 'timestamp', 'date', 'datetime', 'ts']
    time_col = next((col for col in time_candidates if col in df.columns), None)
    if not time_col:
        print("ERROR: No time column found.")
        sys.exit(1)

    symbol_col = 'symbol' if 'symbol' in df.columns else None
    if not symbol_col:
        print("ERROR: No 'symbol' column found.")
        sys.exit(1)

    # Convert time
    if pd.api.types.is_numeric_dtype(df[time_col]):
        df[time_col] = pd.to_datetime(df[time_col], unit='s', errors='coerce')
    else:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')

    df = df.dropna(subset=[time_col]).sort_values(time_col)
    df = df.groupby([time_col, symbol_col])['close'].last().reset_index()

    # Extract series
    price1 = df[df[symbol_col].str.upper() == sym1].set_index(time_col)['close'].rename(sym1)
    price2 = df[df[symbol_col].str.upper() == sym2].set_index(time_col)['close'].rename(sym2)

    # === MAXIMUM OVERLAP ALIGNMENT ===
    prices = pd.concat([price1, price2], axis=1, sort=False).dropna()

    print(f"Aligned overlapping hourly data points: {len(prices):,} (~{len(prices)/24/365:.2f} years)")

    # === NEW: Clear date information (super useful for partial-history tokens) ===
    if len(prices) > 0:
        overlap_start = prices.index.min()
        overlap_end   = prices.index.max()
        days_overlap  = (overlap_end - overlap_start).days
        print(f"Overlap period          : {overlap_start.date()} → {overlap_end.date()} ({days_overlap} days)")
        print(f"{sym1} full history     : {price1.index.min().date()} → {price1.index.max().date()} ({len(price1):,} hours)")
        print(f"{sym2} full history     : {price2.index.min().date()} → {price2.index.max().date()} ({len(price2):,} hours)")

    if len(prices) < 500:
        print("⚠️  Warning: Very short overlapping period — results may be noisy.")

    # Log returns (industry gold standard)
    log_returns = np.log(prices / prices.shift(1)).dropna()

    pearson_corr = log_returns[sym1].corr(log_returns[sym2], method='pearson')
    spearman_corr = log_returns[sym1].corr(log_returns[sym2], method='spearman')

    # Daily version
    daily_prices = prices.resample('D').last()
    daily_logret = np.log(daily_prices / daily_prices.shift(1)).dropna()
    daily_pearson = daily_logret[sym1].corr(daily_logret[sym2])

    # Results
    print("\n" + "="*70)
    print(f"INDUSTRY-STANDARD CORRELATION: {sym1} vs {sym2}")
    print("="*70)
    print(f"Hourly Pearson (log returns) : {pearson_corr:6.4f}")
    print(f"Hourly Spearman (rank)       : {spearman_corr:6.4f}")
    print(f"Daily Pearson (log returns)  : {daily_pearson:6.4f}")
    print("="*70)

    abs_corr = abs(pearson_corr)
    strength = "VERY STRONG" if abs_corr > 0.8 else "STRONG" if abs_corr > 0.6 else "MODERATE" if abs_corr > 0.4 else "WEAK"
    direction = "positive" if pearson_corr > 0 else "negative"
    print(f"→ Interpretation: {strength} {direction} correlation")

if __name__ == "__main__":
    main()
