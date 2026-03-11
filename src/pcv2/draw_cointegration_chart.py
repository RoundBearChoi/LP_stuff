import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import adfuller
import os

class CointegrationChart:
    """
    Clean, reusable class for generating the full 5-chart cointegration analysis.
    - Works exactly like before from the command line
    - Defaults to ETH/BTC if no arguments are provided (super convenient!)
    - Emojis ONLY in console output
    - dpi=200
    - No plt.show() → instant run
    - FIXED LAYOUT: verdict box inside Chart 1 (Beta → ADF p-value → Verdict)
    """

    DEFAULT_CSV = "top100_hourly_1year_combined.csv"
    ROLLING_WINDOW_DAYS = 90

    def __init__(self, sym1: str, sym2: str, csv_file: str = None):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.csv_file = csv_file or self.DEFAULT_CSV

        self.p1 = None
        self.p2 = None
        self.beta = None
        self.spread = None
        self.zscore = None
        self.p_value = None
        self.verdict_console = ""
        self.verdict_chart = ""
        self.box_color = ""

    def _load_data(self):
        if not os.path.exists(self.csv_file):
            print(f"❌ File '{self.csv_file}' not found!")
            sys.exit(1)

        df = pd.read_csv(self.csv_file, parse_dates=['datetime'])
        df_pair = df[df['symbol'].isin([self.sym1, self.sym2])].copy()
        pivot = df_pair.pivot(index='datetime', columns='symbol', values='close').dropna()

        if self.sym1 not in pivot.columns or self.sym2 not in pivot.columns:
            print(f"❌ Symbols not found. Available: {list(pivot.columns)}")
            sys.exit(1)

        self.p1 = pivot[self.sym1]
        self.p2 = pivot[self.sym2]

        print(f"Data range for {self.sym1}/{self.sym2}: "
              f"{self.p1.index[0].date()} → {self.p1.index[-1].date()} "
              f"({len(self.p1):,} hourly rows)")

    def _compute_full_sample(self):
        log_p1 = np.log(self.p1)
        log_p2 = np.log(self.p2)

        X = add_constant(log_p2)
        model = OLS(log_p1, X).fit()
        self.beta = model.params.iloc[1]
        self.spread = log_p1 - self.beta * log_p2
        self.zscore = (self.spread - self.spread.mean()) / self.spread.std()

        adf = adfuller(self.spread, maxlag=1, regression='c')
        self.p_value = adf[1]

        if self.p_value < 0.01:
            self.verdict_console = "✅ STRONG COINTEGRATION (p < 0.01)"
            self.verdict_chart = "STRONG COINTEGRATION (p < 0.01)"
            self.box_color = 'lime'
        elif self.p_value < 0.05:
            self.verdict_console = "✅ MODERATE COINTEGRATION (p < 0.05)"
            self.verdict_chart = "MODERATE COINTEGRATION (p < 0.05)"
            self.box_color = 'lightgreen'
        elif self.p_value < 0.10:
            self.verdict_console = "⚠️ WEAK / MARGINAL (p < 0.10)"
            self.verdict_chart = "WEAK / MARGINAL (p < 0.10)"
            self.box_color = 'yellow'
        else:
            self.verdict_console = "❌ NO COINTEGRATION (p ≥ 0.10)"
            self.verdict_chart = "NO COINTEGRATION (p ≥ 0.10)"
            self.box_color = 'salmon'

        print("\n=== FULL-SAMPLE RESULTS ===")
        print(f"Hedge ratio (beta): {self.beta:.4f}")
        print(f"ADF p-value: {self.p_value:.6f} → {self.verdict_console}")

    def _compute_rolling(self):
        print("\nComputing rolling cointegration (90-day windows, updated daily)...")
        window = self.ROLLING_WINDOW_DAYS * 24
        step = 24

        log_p1 = np.log(self.p1)
        log_p2 = np.log(self.p2)

        self.rolling_dates = []
        self.rolling_betas = []
        self.rolling_pvals = []

        for i in range(0, len(log_p1) - window + 1, step):
            log_p1_win = log_p1.iloc[i:i + window]
            log_p2_win = log_p2.iloc[i:i + window]

            X_win = add_constant(log_p2_win)
            model_win = OLS(log_p1_win, X_win).fit()
            beta_win = model_win.params.iloc[1]

            spread_win = log_p1_win - beta_win * log_p2_win
            adf_win = adfuller(spread_win, maxlag=1, regression='c')

            self.rolling_betas.append(beta_win)
            self.rolling_pvals.append(adf_win[1])
            self.rolling_dates.append(log_p1.index[i + window - 1])

        print(f"Rolling windows computed: {len(self.rolling_dates)}")

    def _create_ratio_stats(self):
        self.ratio = self.p1 / self.p2
        self.ratio_rolling_mean = self.ratio.rolling(window=720, min_periods=1).mean()
        self.ratio_rolling_std = self.ratio.rolling(window=720, min_periods=1).std()

    def generate(self):
        """Main method — everything + instant PNG save, no warning, no pause"""
        self._load_data()
        self._compute_full_sample()
        self._compute_rolling()
        self._create_ratio_stats()

        # ====================== 5 CHARTS ======================
        fig, axs = plt.subplots(5, 1, figsize=(14, 28),
                                sharex=True,
                                gridspec_kw={'hspace': 0.48},
                                constrained_layout=False)

        fig.subplots_adjust(top=0.905, bottom=0.05, left=0.07, right=0.93, hspace=0.48)

        # ==================== CHART 1 (with verdict box) ====================
        norm1 = self.p1 / self.p1.iloc[0] * 100
        norm2 = self.p2 / self.p2.iloc[0] * 100
        axs[0].plot(norm1.index, norm1, label=self.sym1, linewidth=2)
        axs[0].plot(norm2.index, norm2, label=self.sym2, linewidth=2)
        axs[0].set_title(f"1. Normalized Prices — {self.sym1} vs {self.sym2}")
        axs[0].legend(loc='upper left')
        axs[0].grid(True, alpha=0.3)

        # === VERDICT BOX (Beta appears BEFORE ADF p-value) ===
        axs[0].text(0.02, 0.82,
                    f"FULL-SAMPLE RESULTS\n"
                    f"Beta = {self.beta:.4f}\n"
                    f"ADF p-value = {self.p_value:.5f}\n"
                    f"{self.verdict_chart}",
                    transform=axs[0].transAxes,
                    fontsize=13.5, ha='left', va='top', fontweight='bold',
                    bbox=dict(boxstyle="round,pad=1.0", facecolor=self.box_color,
                              alpha=0.95, edgecolor='black'))

        # ==================== CHARTS 2–5 ====================
        axs[1].plot(self.ratio.index, self.ratio, label=f"{self.sym1}/{self.sym2} Ratio",
                    color='purple', linewidth=2)
        axs[1].plot(self.ratio_rolling_mean.index, self.ratio_rolling_mean,
                    label='~30-day Rolling Mean', color='orange', linewidth=2)
        axs[1].fill_between(self.ratio.index,
                            self.ratio_rolling_mean - 2 * self.ratio_rolling_std,
                            self.ratio_rolling_mean + 2 * self.ratio_rolling_std,
                            color='orange', alpha=0.15)
        axs[1].set_title("2. Price Ratio")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)

        axs[2].plot(self.spread.index, self.spread, label='Spread', color='blue', linewidth=2)
        axs[2].axhline(self.spread.mean(), color='red', linestyle='--', label='Mean')
        axs[2].fill_between(self.spread.index,
                            self.spread.mean() - 2 * self.spread.std(),
                            self.spread.mean() + 2 * self.spread.std(),
                            color='red', alpha=0.12)
        axs[2].set_title(f"3. Spread = log({self.sym1}) − {self.beta:.4f} × log({self.sym2})")
        axs[2].legend()
        axs[2].grid(True, alpha=0.3)

        axs[3].plot(self.zscore.index, self.zscore, label='Z-Score', color='darkgreen', linewidth=2)
        axs[3].axhline(0, color='black', linestyle='--')
        axs[3].axhline(2, color='red', linestyle='--', label='+2/-2 Entry')
        axs[3].axhline(-2, color='red', linestyle='--')
        axs[3].axhline(1, color='orange', linestyle='--', label='+1/-1 Exit')
        axs[3].axhline(-1, color='orange', linestyle='--')
        axs[3].set_title("4. Z-Score of Spread")
        axs[3].legend(fontsize=10)
        axs[3].grid(True, alpha=0.3)
        axs[3].set_ylim(-5, 5)

        ax_beta = axs[4]
        ax_p = ax_beta.twinx()
        ax_beta.plot(self.rolling_dates, self.rolling_betas, color='blue', linewidth=2,
                     label='Rolling Beta (hedge ratio)')
        ax_p.plot(self.rolling_dates, self.rolling_pvals, color='red', linewidth=2,
                  label='Rolling ADF p-value')

        pvals_arr = np.array(self.rolling_pvals)
        dates_arr = pd.to_datetime(self.rolling_dates)
        mask = pvals_arr < 0.05
        ax_p.fill_between(dates_arr, 0, 0.05, where=mask, color='lightgreen', alpha=0.4,
                          label='Cointegrated window (p<0.05)')

        ax_p.axhline(0.01, color='darkgreen', linestyle='--', alpha=0.7)
        ax_p.axhline(0.05, color='green', linestyle='--', linewidth=2, label='p=0.05 threshold')
        ax_p.axhline(0.10, color='orange', linestyle='--', alpha=0.7)

        ax_beta.set_ylabel('Rolling Beta', color='blue')
        ax_p.set_ylabel('Rolling ADF p-value', color='red')
        ax_beta.set_title("5. Rolling Cointegration (90-day windows) — Beta & ADF p-value")
        ax_beta.grid(True, alpha=0.3)

        lines1, labels1 = ax_beta.get_legend_handles_labels()
        lines2, labels2 = ax_p.get_legend_handles_labels()
        ax_beta.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

        fig.suptitle(f"COINTEGRATION ANALYSIS: {self.sym1} vs {self.sym2} — "
                     f"{len(self.p1):,} hourly bars "
                     f"({self.p1.index[0].date()} to {self.p1.index[-1].date()})",
                     fontsize=15.5, y=0.965)

        output_file = f"cointegration_{self.sym1}_{self.sym2}_with_rolling.png"
        plt.savefig(output_file, dpi=200, bbox_inches='tight')
        plt.close(fig)
        print(f"\n✅ Saved: {output_file} (Beta-first verdict box + ETH/BTC default support)")

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
        # Default fallback as requested
        csv_file = None
        sym1 = "ETH"
        sym2 = "BTC"
        print("⚡ No symbols provided → Using default pair: ETH / BTC")
    else:
        print(f"Usage: python {sys.argv[0]} [CSV_FILE] SYM1 SYM2")
        print("   Example: python draw_cointegration_chart.py ETH SOL")
        print("   No arguments → automatically defaults to ETH/BTC")
        sys.exit(1)

    chart = CointegrationChart(sym1, sym2, csv_file)
    chart.generate()
