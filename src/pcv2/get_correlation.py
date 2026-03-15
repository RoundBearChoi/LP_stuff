import pandas as pd
import numpy as np
import sys
import warnings
from pathlib import Path
#from config import DEFAULT_MAX_MONTHS, DEFAULT_CSV_FILE
from config import DEFAULT_COINTEGRATION_CORRELATION_MONTHS as DEFAULT_MAX_MONTHS, DEFAULT_CSV_FILE

# Silence the pandas concat FutureWarning permanently
warnings.filterwarnings("ignore", message="Sorting by default when concatenating all DatetimeIndex")


class CorrelationAnalyzer:
    """Computes industry-standard price correlation between two crypto symbols."""

    def __init__(self, sym1: str, sym2: str, file_path: str = DEFAULT_CSV_FILE, max_months: int = DEFAULT_MAX_MONTHS):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.file_path = file_path
        self.max_months = max_months

    def run(self):
        """Main execution method — contains all original logic from main()."""
        if not Path(self.file_path).exists():
            print(f"Error: File '{self.file_path}' not found.")
            sys.exit(1)

        print(f"Loading {self.file_path} and computing {self.sym1} vs {self.sym2} correlation...")

        df = pd.read_csv(self.file_path)
        print(f"Loaded {len(df):,} rows. Columns detected: {df.columns.tolist()}")

        # Auto-detect time column
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

        # === IMPROVED MAXIMUM TIMEFRAME FILTER (30.437 days per month) ===
        end_date = df[time_col].max()
        days_back = int(self.max_months * 30.437)
        start_date = end_date - pd.Timedelta(days=days_back)
        df = df[df[time_col] >= start_date].copy()
        print(f"Filtered to last {self.max_months} months: {df[time_col].min().date()} → {end_date.date()}")
        print(f"Rows after filter: {len(df):,}")

        df = df.groupby([time_col, symbol_col])['close'].last().reset_index()

        # Extract series
        price1 = df[df[symbol_col].str.upper() == self.sym1].set_index(time_col)['close'].rename(self.sym1)
        price2 = df[df[symbol_col].str.upper() == self.sym2].set_index(time_col)['close'].rename(self.sym2)

        # === MAXIMUM OVERLAP ALIGNMENT ===
        prices = pd.concat([price1, price2], axis=1, sort=False).dropna()

        print(f"Aligned overlapping hourly data points: {len(prices):,} (~{len(prices)/24/365:.2f} years)")

        if len(prices) > 0:
            overlap_start = prices.index.min()
            overlap_end   = prices.index.max()
            days_overlap  = (overlap_end - overlap_start).days
            print(f"Overlap period          : {overlap_start.date()} → {overlap_end.date()} ({days_overlap} days)")

        if len(prices) < 500:
            print("⚠️  Warning: Very short overlapping period — results may be noisy.")

        # Log returns
        log_returns = np.log(prices / prices.shift(1)).dropna()

        pearson_corr = log_returns[self.sym1].corr(log_returns[self.sym2], method='pearson')
        spearman_corr = log_returns[self.sym1].corr(log_returns[self.sym2], method='spearman')

        # Daily version
        daily_prices = prices.resample('D').last()
        daily_logret = np.log(daily_prices / daily_prices.shift(1)).dropna()
        daily_pearson = daily_logret[self.sym1].corr(daily_logret[self.sym2])

        self.prices = prices
        self.log_returns = log_returns
        self.daily_prices = daily_prices
        self.daily_logret = daily_logret

        # Results
        print("\n" + "="*70)
        print(f"INDUSTRY-STANDARD CORRELATION: {self.sym1} vs {self.sym2} (last {self.max_months} months)")
        print("="*70)
        print(f"Hourly Pearson (log returns) : {pearson_corr:6.4f}")
        print(f"Hourly Spearman (rank)       : {spearman_corr:6.4f}")
        print(f"Daily Pearson (log returns)  : {daily_pearson:6.4f}")
        print("="*70)

        abs_corr = abs(pearson_corr)
        strength = "VERY STRONG" if abs_corr > 0.8 else "STRONG" if abs_corr > 0.6 else "MODERATE" if abs_corr > 0.4 else "WEAK"
        direction = "positive" if pearson_corr > 0 else "negative"
        print(f"→ Interpretation: {strength} {direction}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(f"No symbols provided — defaulting to ETH vs BTC (last {DEFAULT_MAX_MONTHS} months)\n")
        sym1 = "ETH"
        sym2 = "BTC"
        file_path = DEFAULT_CSV_FILE
        max_months = DEFAULT_MAX_MONTHS

    else:
        args = sys.argv[1:]
        max_months = DEFAULT_MAX_MONTHS
        if args and args[-1].isdigit():
            max_months = int(args.pop())

        if len(args) == 0:
            print(f"No symbols provided — defaulting to ETH vs BTC (last {max_months} months)\n")
            sym1 = "ETH"
            sym2 = "BTC"
            file_path = DEFAULT_CSV_FILE
        elif len(args) == 1:
            print("Usage: python get_correlation.py <symbol1> <symbol2> [csv_file] [max_months]")
            print("Example: python get_correlation.py pump sol 3")
            sys.exit(1)
        elif len(args) == 2:
            sym1 = args[0]
            sym2 = args[1]
            file_path = DEFAULT_CSV_FILE
        elif len(args) == 3:
            sym1 = args[0]
            sym2 = args[1]
            file_path = args[2]
        else:
            print("Usage: python get_correlation.py <symbol1> <symbol2> [csv_file] [max_months]")
            sys.exit(1)

    analyzer = CorrelationAnalyzer(sym1, sym2, file_path, max_months)
    analyzer.run()
