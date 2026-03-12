import pandas as pd
import numpy as np
import sys
from pathlib import Path

def main():
    # Usage: python get_correlation.py eth btc
    #        python get_correlation.py eth btc path/to/yourfile.csv
    if len(sys.argv) < 3:
        print("Usage: python get_correlation.py <symbol1> <symbol2> [csv_file]")
        print("Example: python get_correlation.py eth btc")
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

    # === AUTO-DETECT COMMON COLUMN NAMES (very flexible) ===
    # Your CSV almost certainly has one of these for time
    time_candidates = ['time', 'timestamp', 'date', 'datetime', 'ts']
    time_col = next((col for col in time_candidates if col in df.columns), None)
    if not time_col:
        print("ERROR: No time column found. Edit the 'time_candidates' list or tell me your exact column name.")
        sys.exit(1)

    symbol_col = 'symbol' if 'symbol' in df.columns else None
    if not symbol_col:
        print("ERROR: No 'symbol' column found.")
        sys.exit(1)

    # Convert time (handles both Unix seconds and string dates)
    if pd.api.types.is_numeric_dtype(df[time_col]):
        df[time_col] = pd.to_datetime(df[time_col], unit='s', errors='coerce')
    else:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')

    df = df.dropna(subset=[time_col]).sort_values(time_col)

    # Optional: deduplicate in case any hour has duplicate entries
    df = df.groupby([time_col, symbol_col])['close'].last().reset_index()

    # === EXTRACT AND ALIGN THE TWO SERIES ===
    price1 = df[df[symbol_col].str.upper() == sym1].set_index(time_col)['close'].rename(sym1)
    price2 = df[df[symbol_col].str.upper() == sym2].set_index(time_col)['close'].rename(sym2)

    prices = pd.concat([price1, price2], axis=1).dropna()
    print(f"Aligned overlapping hourly data points: {len(prices):,} (~{len(prices)/24/365:.1f} years)")

    if len(prices) < 500:
        print("Warning: Very short overlapping period — results may be noisy.")

    # === INDUSTRY GOLD STANDARD: LOG RETURNS ===
    log_returns = np.log(prices / prices.shift(1)).dropna()

    pearson_corr = log_returns[sym1].corr(log_returns[sym2], method='pearson')
    spearman_corr = log_returns[sym1].corr(log_returns[sym2], method='spearman')

    # Daily version (many analysts prefer this for cleaner signal)
    daily_prices = prices.resample('D').last()
    daily_logret = np.log(daily_prices / daily_prices.shift(1)).dropna()
    daily_pearson = daily_logret[sym1].corr(daily_logret[sym2])

    # === RESULTS ===
    print("\n" + "="*60)
    print(f"INDUSTRY-STANDARD CORRELATION: {sym1} vs {sym2}")
    print("="*60)
    print(f"Hourly Pearson (log returns) : {pearson_corr:6.4f}")
    print(f"Hourly Spearman (rank)       : {spearman_corr:6.4f}")
    print(f"Daily Pearson (log returns)  : {daily_pearson:6.4f}")
    print("="*60)

    # Interpretation guide
    abs_corr = abs(pearson_corr)
    if abs_corr > 0.8:
        strength = "VERY STRONG"
    elif abs_corr > 0.6:
        strength = "STRONG"
    elif abs_corr > 0.4:
        strength = "MODERATE"
    else:
        strength = "WEAK"
    direction = "positive" if pearson_corr > 0 else "negative"
    print(f"→ Interpretation: {strength} {direction} correlation")
    print("   (Values >0.7 are typical for BTC-ETH; lower = better diversification)")

if __name__ == "__main__":
    main()
