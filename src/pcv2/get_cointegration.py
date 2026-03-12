import sys
import pandas as pd
import numpy as np
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import coint
import os
from dataclasses import dataclass
from typing import Optional, Tuple

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
    DEFAULT_CSV = "top100_hourly_1year_combined.csv"
    ROLLING_WINDOW_DAYS = 90

    def __init__(self, sym1: str, sym2: str, csv_file: Optional[str] = None):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.csv_file = csv_file or self.DEFAULT_CSV
        self.results: Optional[CointegrationResults] = None

    def _load_data(self) -> Tuple[pd.Series, pd.Series]:
        if not os.path.exists(self.csv_file):
            print(f"❌ File '{self.csv_file}' not found!")
            sys.exit(1)

        df = pd.read_csv(self.csv_file, parse_dates=['datetime'])
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
        log_p1 = np.log(p1)
        log_p2 = np.log(p2)

        # === Beta & spread ===
        X = add_constant(log_p2)
        model = OLS(log_p1, X).fit()
        beta = model.params.iloc[1]
        spread = log_p1 - beta * log_p2
        zscore = (spread - spread.mean()) / spread.std()

        # === Cointegration test ===
        _, p_value, _ = coint(log_p1, log_p2, autolag='AIC')

        # === Half-life ===
        lagged = spread.shift(1).dropna()
        delta = spread.diff().dropna()
        ou_model = OLS(delta, add_constant(lagged)).fit()
        kappa = -ou_model.params.iloc[1]
        half_life_hours = np.log(2) / kappa if kappa > 1e-8 else float('inf')
        half_life_days = half_life_hours / 24

        # === Verdict ===
        if p_value < 0.01:
            verdict_console = "✅ STRONG COINTEGRATION (p < 0.01)"
            verdict_chart = "STRONG COINTEGRATION (p < 0.01)"
            box_color = 'lime'
        elif p_value < 0.05:
            verdict_console = "✅ MODERATE COINTEGRATION (p < 0.05)"
            verdict_chart = "MODERATE COINTEGRATION (p < 0.05)"
            box_color = 'lightgreen'
        elif p_value < 0.10:
            verdict_console = "⚠️ WEAK / MARGINAL (p < 0.10)"
            verdict_chart = "WEAK / MARGINAL (p < 0.10)"
            box_color = 'yellow'
        else:
            verdict_console = "❌ NO COINTEGRATION (p ≥ 0.10)"
            verdict_chart = "NO COINTEGRATION (p ≥ 0.10)"
            box_color = 'salmon'

        # === Print the exact block you asked for ===
        print("\n=== FULL-SAMPLE RESULTS (GOLD STANDARD) ===")
        print(f"Hedge ratio (beta): {beta:.4f}")
        print(f"Cointegration p-value: {p_value:.6f}")
        print(f"Half-life: {half_life_days:.1f} days")
        print(f"→ {verdict_console}")

        # === Rolling cointegration ===
        print("\nComputing rolling cointegration (90-day windows, updated daily)...")
        window = self.ROLLING_WINDOW_DAYS * 24
        step = 24
        rolling_dates, rolling_betas, rolling_pvals = [], [], []

        for i in range(0, len(log_p1) - window + 1, step):
            win1, win2 = log_p1.iloc[i:i+window], log_p2.iloc[i:i+window]
            beta_win = OLS(win1, add_constant(win2)).fit().params.iloc[1]
            _, pval_win, _ = coint(win1, win2, autolag='AIC')
            rolling_betas.append(beta_win)
            rolling_pvals.append(pval_win)
            rolling_dates.append(log_p1.index[i + window - 1])

        print(f"Rolling windows computed: {len(rolling_dates)}")

        # === Ratio stats ===
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


# ==================== STANDALONE CLI (now with ETH/BTC default) ====================
if __name__ == "__main__":
    if len(sys.argv) == 4:
        csv_file = sys.argv[1]
        sym1 = sys.argv[2]
        sym2 = sys.argv[3]
    elif len(sys.argv) == 3:
        csv_file = None
        sym1 = sys.argv[1]
        sym2 = sys.argv[2]
    elif len(sys.argv) == 1:
        csv_file = None
        sym1 = "ETH"
        sym2 = "BTC"
        print("⚡ No symbols provided → Using default pair: ETH / BTC")
    else:
        print(f"Usage: python {sys.argv[0]} [CSV_FILE] SYM1 SYM2")
        print("   Example: python get_cointegration.py ETH SOL")
        print("   No arguments → automatically defaults to ETH/BTC")
        sys.exit(1)

    analyzer = CointegrationAnalyzer(sym1, sym2, csv_file)
    analyzer.compute()
    print(f"\n✅ Analysis complete for {sym1}/{sym2}")
