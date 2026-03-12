import matplotlib.pyplot as plt
import pandas as pd          # ← ADDED
import numpy as np           # ← ADDED
from get_cointegration import CointegrationAnalyzer


class CointegrationChart:
    """Only responsible for visualization. All heavy lifting is done by the analyzer."""

    def __init__(self, sym1: str, sym2: str, csv_file: str = None):
        self.analyzer = CointegrationAnalyzer(sym1, sym2, csv_file)

    def generate(self):
        # === 1. Compute everything (one clean call) ===
        results = self.analyzer.compute()

        # ====================== 5 CHARTS ======================
        fig, axs = plt.subplots(5, 1, figsize=(14, 28),
                                sharex=True,
                                gridspec_kw={'hspace': 0.48},
                                constrained_layout=False)

        fig.subplots_adjust(top=0.905, bottom=0.05, left=0.07, right=0.93, hspace=0.48)

        # CHART 1 – Normalized Prices + Verdict Box
        norm1 = results.p1 / results.p1.iloc[0] * 100
        norm2 = results.p2 / results.p2.iloc[0] * 100
        axs[0].plot(norm1.index, norm1, label=self.analyzer.sym1, linewidth=2)
        axs[0].plot(norm2.index, norm2, label=self.analyzer.sym2, linewidth=2)
        axs[0].set_title(f"1. Normalized Prices — {self.analyzer.sym1} vs {self.analyzer.sym2}")
        axs[0].legend(loc='upper left')
        axs[0].grid(True, alpha=0.3)

        axs[0].text(0.02, 0.80,
                    f"Beta = {results.beta:.4f}\n"
                    f"Half-life ≈ {results.half_life_days:.1f} days\n"
                    f"Cointegration p-value = {results.p_value:.5f}\n"
                    f"{results.verdict_chart}",
                    transform=axs[0].transAxes,
                    fontsize=12.8, ha='left', va='top', fontweight='bold',
                    bbox=dict(boxstyle="round,pad=1.0", facecolor=results.box_color,
                              alpha=0.95, edgecolor='black'))

        # CHART 2 – Price Ratio
        axs[1].plot(results.ratio.index, results.ratio,
                    label=f"{self.analyzer.sym1}/{self.analyzer.sym2} Ratio",
                    color='purple', linewidth=2)
        axs[1].plot(results.ratio_rolling_mean.index, results.ratio_rolling_mean,
                    label='~30-day Rolling Mean', color='orange', linewidth=2)
        axs[1].fill_between(results.ratio.index,
                            results.ratio_rolling_mean - 2 * results.ratio_rolling_std,
                            results.ratio_rolling_mean + 2 * results.ratio_rolling_std,
                            color='orange', alpha=0.15)
        axs[1].set_title("2. Price Ratio")
        axs[1].legend()
        axs[1].grid(True, alpha=0.3)

        # CHART 3 – Spread
        axs[2].plot(results.spread.index, results.spread, label='Spread',
                    color='blue', linewidth=2)
        axs[2].axhline(results.spread.mean(), color='red', linestyle='--', label='Mean')
        axs[2].fill_between(results.spread.index,
                            results.spread.mean() - 2 * results.spread.std(),
                            results.spread.mean() + 2 * results.spread.std(),
                            color='red', alpha=0.12)
        axs[2].set_title(f"3. Spread = log({self.analyzer.sym1}) − {results.beta:.4f} × log({self.analyzer.sym2})")
        axs[2].legend()
        axs[2].grid(True, alpha=0.3)

        # CHART 4 – Z-Score
        axs[3].plot(results.zscore.index, results.zscore, label='Z-Score',
                    color='darkgreen', linewidth=2)
        axs[3].axhline(0, color='black', linestyle='--')
        axs[3].axhline(2, color='red', linestyle='--', label='+2/-2 Entry')
        axs[3].axhline(-2, color='red', linestyle='--')
        axs[3].axhline(1, color='orange', linestyle='--', label='+1/-1 Exit')
        axs[3].axhline(-1, color='orange', linestyle='--')
        axs[3].set_title("4. Z-Score of Spread")
        axs[3].legend(fontsize=10)
        axs[3].grid(True, alpha=0.3)
        axs[3].set_ylim(-5, 5)

        # CHART 5 – Rolling Beta & p-value
        ax_beta = axs[4]
        ax_p = ax_beta.twinx()
        ax_beta.plot(results.rolling_dates, results.rolling_betas,
                     color='blue', linewidth=2, label='Rolling Beta (hedge ratio)')
        ax_p.plot(results.rolling_dates, results.rolling_pvals,
                  color='red', linewidth=2, label='Rolling Cointegration p-value')

        dates_arr = pd.to_datetime(results.rolling_dates)          # ← now works
        mask = np.array(results.rolling_pvals) < 0.05              # ← now works
        ax_p.fill_between(dates_arr, 0, 0.05, where=mask,
                          color='lightgreen', alpha=0.4,
                          label='Cointegrated window (p<0.05)')

        ax_p.axhline(0.01, color='darkgreen', linestyle='--', alpha=0.7)
        ax_p.axhline(0.05, color='green', linestyle='--', linewidth=2, label='p=0.05 threshold')
        ax_p.axhline(0.10, color='orange', linestyle='--', alpha=0.7)

        ax_beta.set_ylabel('Rolling Beta', color='blue')
        ax_p.set_ylabel('Rolling Cointegration p-value', color='red')
        ax_beta.set_title("5. Rolling Cointegration (90-day windows) — Beta & p-value")
        ax_beta.grid(True, alpha=0.3)

        lines1, labels1 = ax_beta.get_legend_handles_labels()
        lines2, labels2 = ax_p.get_legend_handles_labels()
        ax_beta.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)

        fig.suptitle(f"COINTEGRATION ANALYSIS (GOLD STANDARD): {self.analyzer.sym1} vs {self.analyzer.sym2} — "
                     f"{len(results.p1):,} hourly bars "
                     f"({results.p1.index[0].date()} to {results.p1.index[-1].date()})",
                     fontsize=15.5, y=0.965)

        output_file = f"cointegration_{self.analyzer.sym1}_{self.analyzer.sym2}_with_rolling.png"
        plt.savefig(output_file, dpi=200, bbox_inches='tight')
        plt.close(fig)
        print(f"\n✅ Saved: {output_file}")


if __name__ == "__main__":
    # Same CLI as before — no breaking changes!
    import sys
    if len(sys.argv) == 4:
        csv_file, sym1, sym2 = sys.argv[1], sys.argv[2], sys.argv[3]
    elif len(sys.argv) == 3:
        csv_file, sym1, sym2 = None, sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 1:
        csv_file, sym1, sym2 = None, "ETH", "BTC"
        print("⚡ No symbols provided → Using default pair: ETH / BTC")
    else:
        print(f"Usage: python {sys.argv[0]} [CSV_FILE] SYM1 SYM2")
        sys.exit(1)

    chart = CointegrationChart(sym1, sym2, csv_file)
    chart.generate()
