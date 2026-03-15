import sys
import pandas as pd
import numpy as np
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import coint
import os
from dataclasses import dataclass
from typing import Optional, Tuple
from cointegration_engine import compute_cointegration, CointegrationMethod
from config import DEFAULT_COINTEGRATION_CORRELATION_MONTHS as DEFAULT_MAX_MONTHS, DEFAULT_CSV_FILE


@dataclass
class CointegrationResults:
    """All results in one clean object."""
    p1: pd.Series
    p2: pd.Series
    beta: float
    spread: pd.Series
    zscore: pd.Series
    p_value: float
    half_life_days: float
    verdict_console: str
    verdict_chart: str
    box_color: str
    rolling_dates: list
    rolling_betas: list
    rolling_pvals: list
    ratio: pd.Series
    ratio_rolling_mean: pd.Series
    ratio_rolling_std: pd.Series


class CointegrationAnalyzer:
    DEFAULT_CSV = DEFAULT_CSV_FILE
    ROLLING_WINDOW_DAYS = 90

    def __init__(self, sym1: str, sym2: str, csv_file: Optional[str] = None, max_months: int = DEFAULT_MAX_MONTHS):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.csv_file = csv_file or self.DEFAULT_CSV
        self.max_months = max_months
        self.results: Optional[CointegrationResults] = None

    def _load_data(self) -> Tuple[pd.Series, pd.Series]:
        if not os.path.exists(self.csv_file):
            print(f"❌ File '{self.csv_file}' not found!")
            sys.exit(1)

        df = pd.read_csv(self.csv_file, parse_dates=['datetime'])

        # === IMPROVED MAXIMUM TIMEFRAME FILTER (30.437 days per month) ===
        end_date = df['datetime'].max()
        days_back = int(self.max_months * 30.437)
        start_date = end_date - pd.Timedelta(days=days_back)
        df = df[df['datetime'] >= start_date].copy()
        print(f"Filtered to last {self.max_months} months: {df['datetime'].min().date()} → {end_date.date()}")
        print(f"Rows after filter: {len(df):,}")

        df_pair = df[df['symbol'].isin([self.sym1, self.sym2])].copy()
        pivot = df_pair.pivot(index='datetime', columns='symbol', values='close').dropna()

        if self.sym1 not in pivot.columns or self.sym2 not in pivot.columns:
            print(f"❌ Symbols not found. Available: {list(pivot.columns)}")
            sys.exit(1)

        p1 = pivot[self.sym1]
        p2 = pivot[self.sym2]

        print(f"Data range for {self.sym1}/{self.sym2}: "
              f"{p1.index[0].date()} → {p1.index[-1].date()} "
              f"({len(p1):,} hourly rows)")
        return p1, p2

    def compute(self) -> CointegrationResults:
        """Runs the full gold-standard analysis and prints the exact console block."""
        p1, p2 = self._load_data()

        # === NOW FROM THE CENTRAL COINTEGRATION ENGINE ===
        # Change ENGLE_GRANGER → JOHANSEN anytime you want to test the new method
        eg = compute_cointegration(p1, p2, method=CointegrationMethod.ENGLE_GRANGER)

        beta = eg.beta
        spread = eg.spread
        zscore = eg.zscore
        p_value = eg.p_value
        half_life_days = eg.half_life_days
        verdict_console = eg.verdict_console
        verdict_chart = eg.verdict_chart
        box_color = eg.box_color

        # === Verdict print (unchanged) ===
        print(f"\n=== FULL-SAMPLE RESULTS (GOLD STANDARD) — LAST {self.max_months} MONTHS ===")
        print(f"Hedge ratio (beta): {beta:.4f}")
        print(f"Cointegration p-value: {p_value:.6f}")
        print(f"Half-life: {half_life_days:.1f} days")
        print(f"→ {verdict_console}")

        # === Rolling cointegration (unchanged — still uses raw OLS+coint) ===
        print(f"\nComputing rolling cointegration ({self.ROLLING_WINDOW_DAYS}-day windows, updated daily) on last {self.max_months} months...")
        window = self.ROLLING_WINDOW_DAYS * 24
        step = 24
        rolling_dates, rolling_betas, rolling_pvals = [], [], []

        log_p1 = np.log(p1)
        log_p2 = np.log(p2)

        for i in range(0, len(log_p1) - window + 1, step):
            win1, win2 = log_p1.iloc[i:i+window], log_p2.iloc[i:i+window]
            beta_win = OLS(win1, add_constant(win2)).fit().params.iloc[1]
            _, pval_win, _ = coint(win1, win2, autolag='AIC')
            rolling_betas.append(beta_win)
            rolling_pvals.append(pval_win)
            rolling_dates.append(log_p1.index[i + window - 1])

        print(f"Rolling windows computed: {len(rolling_dates)}")

        # === Ratio stats (unchanged) ===
        ratio = p1 / p2
        ratio_rolling_mean = ratio.rolling(window=720, min_periods=1).mean()
        ratio_rolling_std = ratio.rolling(window=720, min_periods=1).std()

        self.results = CointegrationResults(
            p1=p1, p2=p2, beta=beta, spread=spread, zscore=zscore,
            p_value=p_value, half_life_days=half_life_days,
            verdict_console=verdict_console, verdict_chart=verdict_chart,
            box_color=box_color,
            rolling_dates=rolling_dates, rolling_betas=rolling_betas,
            rolling_pvals=rolling_pvals,
            ratio=ratio, ratio_rolling_mean=ratio_rolling_mean,
            ratio_rolling_std=ratio_rolling_std
        )
        return self.results


if __name__ == "__main__":
    csv_file = None
    sym1 = "ETH"
    sym2 = "BTC"
    max_months = DEFAULT_MAX_MONTHS

    if len(sys.argv) == 1:
        print(f"⚡ No symbols provided → Using default pair: ETH / BTC (last {max_months} months)")
    else:
        args = sys.argv[1:]
        if args and args[-1].isdigit():
            max_months = int(args.pop())

        if len(args) == 0:
            print(f"⚡ No symbols provided → Using default pair: ETH / BTC (last {max_months} months)")
        elif len(args) == 2:
            sym1 = args[0].upper()
            sym2 = args[1].upper()
            csv_file = None
        elif len(args) == 3:
            csv_file = args[0]
            sym1 = args[1].upper()
            sym2 = args[2].upper()
        else:
            print(f"Usage: python {sys.argv[0]} [CSV_FILE] SYM1 SYM2 [max_months]")
            print("   Example: python get_cointegration.py ETH SOL 3")
            print("   No arguments → ETH/BTC last 6 months")
            sys.exit(1)

    analyzer = CointegrationAnalyzer(sym1, sym2, csv_file, max_months)
    analyzer.compute()
    print(f"\n✅ Analysis complete for {sym1}/{sym2} (last {max_months} months)")
