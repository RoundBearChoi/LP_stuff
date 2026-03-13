import pandas as pd
import numpy as np
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import coint
import sys
from pathlib import Path
from tqdm import tqdm
import warnings
from config import DEFAULT_MAX_MONTHS, DEFAULT_CSV_FILE

warnings.filterwarnings("ignore")


class AllPairsAnalyzer:
    def __init__(self, file_path: str = DEFAULT_CSV_FILE, target_symbol: str = None, max_months: int = DEFAULT_MAX_MONTHS):
        self.file_path = file_path
        self.target_symbol = target_symbol.upper() if target_symbol else None
        self.max_months = max_months
        self.pivot = None
        self.symbols = None

    def load_data(self):
        if not Path(self.file_path).exists():
            print(f"❌ File '{self.file_path}' not found!")
            sys.exit(1)

        print(f"Loading {self.file_path}...")
        df = pd.read_csv(self.file_path)

        time_candidates = ['time', 'timestamp', 'date', 'datetime', 'ts']
        time_col = next((col for col in time_candidates if col in df.columns), None)
        if not time_col:
            print("ERROR: No time column found.")
            sys.exit(1)
        symbol_col = 'symbol' if 'symbol' in df.columns else None
        if not symbol_col:
            print("ERROR: No 'symbol' column found.")
            sys.exit(1)

        if pd.api.types.is_numeric_dtype(df[time_col]):
            df[time_col] = pd.to_datetime(df[time_col], unit='s', errors='coerce')
        else:
            df[time_col] = pd.to_datetime(df[time_col], errors='coerce')

        df = df.dropna(subset=[time_col]).sort_values(time_col)

        # === IMPROVED MAXIMUM TIMEFRAME FILTER (same as other scripts) ===
        end_date = df[time_col].max()
        days_back = int(self.max_months * 30.437)
        start_date = end_date - pd.Timedelta(days=days_back)
        df = df[df[time_col] >= start_date].copy()
        print(f"Filtered to last {self.max_months} months: {df[time_col].min().date()} → {end_date.date()}")
        print(f"Rows after filter: {len(df):,}")

        df = df.groupby([time_col, symbol_col])['close'].last().reset_index()

        self.pivot = df.pivot(index=time_col, columns=symbol_col, values='close')
        self.symbols = sorted(s.upper() for s in self.pivot.columns)
        
        print(f"✅ Loaded {len(self.symbols)} symbols")
        print(f"   Date range : {self.pivot.index.min().date()} → {self.pivot.index.max().date()}")

        if self.target_symbol:
            if self.target_symbol not in self.symbols:
                print(f"❌ Target symbol '{self.target_symbol}' not found in data.")
                sys.exit(1)
            print(f"🔍 Quick mode activated: {self.target_symbol} vs all others")
        else:
            print(f"🚀 Full mode: all {len(self.symbols)*(len(self.symbols)-1)//2:,} unique pairs")

    # compute_pair() is unchanged — exact same math as before
    def compute_pair(self, sym1: str, sym2: str):
        sub = self.pivot[[sym1, sym2]].dropna()
        n = len(sub)
        if n < 2:
            return None

        overlap_days = (sub.index.max() - sub.index.min()).days
        overlap_hours = n

        try:
            prices = sub.copy()
            logret = np.log(prices / prices.shift(1)).dropna()
            pearson_h = logret[sym1].corr(logret[sym2])
            spearman_h = logret[sym1].corr(logret[sym2], method='spearman')

            daily_p = prices.resample('D').last()
            daily_logret = np.log(daily_p / daily_p.shift(1)).dropna()
            daily_pearson = daily_logret[sym1].corr(daily_logret[sym2]) if len(daily_logret) > 1 else np.nan

            abs_c = abs(pearson_h)
            strength = ("VERY STRONG" if abs_c > 0.8 else
                        "STRONG" if abs_c > 0.6 else
                        "MODERATE" if abs_c > 0.4 else "WEAK")
            direction = "positive" if pearson_h > 0 else "negative"

            # Cointegration (exact same as get_cointegration.py)
            log_p1 = np.log(sub[sym1])
            log_p2 = np.log(sub[sym2])
            X = add_constant(log_p2)
            model = OLS(log_p1, X).fit()
            beta = model.params.iloc[1]

            _, p_value, _ = coint(log_p1, log_p2, autolag='AIC')

            spread = log_p1 - beta * log_p2
            lagged = spread.shift(1).dropna()
            delta = spread.diff().dropna()
            half_life_days = None
            if len(lagged) > 5:
                ou_model = OLS(delta, add_constant(lagged)).fit()
                kappa = -ou_model.params.iloc[1]
                if kappa > 1e-8:
                    half_life_hours = np.log(2) / kappa
                    half_life_days = round(half_life_hours / 24, 1)

            if p_value < 0.01:
                verdict = "STRONG COINTEGRATION (p < 0.01)"
            elif p_value < 0.05:
                verdict = "MODERATE COINTEGRATION (p < 0.05)"
            elif p_value < 0.10:
                verdict = "WEAK / MARGINAL (p < 0.10)"
            else:
                verdict = "NO COINTEGRATION (p ≥ 0.10)"

            return {
                'pair': f"{sym1}-{sym2}",
                'symbol1': sym1,
                'symbol2': sym2,
                'overlap_days': overlap_days,
                'overlap_hours': overlap_hours,
                'overlap_start': str(sub.index.min().date()),
                'overlap_end': str(sub.index.max().date()),
                'hourly_pearson': round(pearson_h, 4),
                'hourly_spearman': round(spearman_h, 4),
                'daily_pearson': round(daily_pearson, 4) if not np.isnan(daily_pearson) else None,
                'correlation_strength': f"{strength} {direction}",
                'abs_corr': round(abs_c, 4),
                'cointegration_pvalue': round(p_value, 6),
                'beta': round(beta, 4),
                'half_life_days': half_life_days,
                'verdict': verdict
            }

        except Exception as e:
            return {
                'pair': f"{sym1}-{sym2}",
                'symbol1': sym1,
                'symbol2': sym2,
                'overlap_days': overlap_days,
                'overlap_hours': overlap_hours,
                'overlap_start': str(sub.index.min().date()),
                'overlap_end': str(sub.index.max().date()),
                'hourly_pearson': None,
                'hourly_spearman': None,
                'daily_pearson': None,
                'correlation_strength': 'ERROR',
                'abs_corr': None,
                'cointegration_pvalue': None,
                'beta': None,
                'half_life_days': None,
                'verdict': f"ERROR: {str(e)[:80]}"
            }

    def run(self):
        self.load_data()
        
        if self.target_symbol:
            others = [s for s in self.symbols if s != self.target_symbol]
            pair_list = [(self.target_symbol, s) for s in sorted(others)]
            output_file = f"{self.target_symbol}_vs_all_pairs_{self.max_months}m.csv"
        else:
            pair_list = [(s1, s2) for i, s1 in enumerate(self.symbols) for s2 in self.symbols[i+1:]]
            output_file = f"all_pairs_cointegration_correlation_{self.max_months}m.csv"

        print(f"\n🚀 Computing {len(pair_list):,} pairs on last {self.max_months} months...")

        results = []
        for sym1, sym2 in tqdm(pair_list, desc="Processing"):
            res = self.compute_pair(sym1, sym2)
            if res:
                results.append(res)

        df = pd.DataFrame(results)
        df = df.sort_values(['cointegration_pvalue', 'abs_corr'], ascending=[True, False]).reset_index(drop=True)

        df.to_csv(output_file, index=False)
        
        print(f"\n✅ Saved {len(df):,} rows to → {output_file}")
        print("\nTop 10 best cointegrations (lowest p-value):")
        print(df.head(10)[['pair', 'overlap_days', 'overlap_hours', 'cointegration_pvalue', 'half_life_days', 'abs_corr', 'verdict']])


if __name__ == "__main__":
    csv_path = DEFAULT_CSV_FILE
    target = None
    max_months = DEFAULT_MAX_MONTHS

    if len(sys.argv) == 4:
        csv_path = sys.argv[1]
        target = sys.argv[2]
        if sys.argv[3].isdigit():
            max_months = int(sys.argv[3])
    elif len(sys.argv) == 3:
        arg1, arg2 = sys.argv[1], sys.argv[2]
        if len(arg1) <= 8 and arg1.replace('-','').isalnum():
            target = arg1
            csv_path = DEFAULT_CSV_FILE
            if arg2.isdigit():
                max_months = int(arg2)
        else:
            csv_path = arg1
            target = arg2
    elif len(sys.argv) == 2:
        arg = sys.argv[1]
        if len(arg) <= 8 and arg.replace('-','').isalnum():
            target = arg
        else:
            csv_path = arg

    analyzer = AllPairsAnalyzer(csv_path, target, max_months)
    analyzer.run()
