import matplotlib.pyplot as plt
import seaborn as sns
import sys
import numpy as np
from get_correlation import CorrelationAnalyzer

sns.set_style("darkgrid")
plt.rcParams.update({'figure.dpi': 160, 'font.size': 11})


class CorrelationChartDrawer:
    def __init__(self, sym1: str, sym2: str, file_path: str = "top100_hourly_1year_combined.csv", max_months: int = 12):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.file_path = file_path
        self.max_months = max_months   # ← NEW (minimal addition)

    def draw(self):
        analyzer = CorrelationAnalyzer(self.sym1, self.sym2, self.file_path, self.max_months)  # ← pass max_months
        analyzer.run()

        if not hasattr(analyzer, 'prices') or len(analyzer.prices) < 200:
            print("⚠️  Not enough overlapping data for meaningful charts.")
            return

        prices = analyzer.prices
        daily_logret = analyzer.daily_logret

        log_prices = np.log(prices)
        hourly_logret = log_prices.diff().dropna()
        hourly_pearson = hourly_logret[self.sym1].corr(hourly_logret[self.sym2])
        hourly_spearman = hourly_logret[self.sym1].corr(hourly_logret[self.sym2], method='spearman')
        daily_pearson = daily_logret[self.sym1].corr(daily_logret[self.sym2])

        if abs(daily_pearson) >= 0.8:
            strength = "Very Strong"
        elif abs(daily_pearson) >= 0.5:
            strength = "Moderate"
        elif abs(daily_pearson) >= 0.3:
            strength = "Weak"
        else:
            strength = "Very Weak"

        fig, axs = plt.subplots(4, 1, figsize=(13, 24), dpi=160)
        fig.suptitle(f"{self.sym1} vs {self.sym2} — Full Correlation Analysis (last {self.max_months} months)\n"
                     f"(Overlap: {len(prices):,} hourly points)  |  "
                     f"Hourly Pearson: {hourly_pearson:.4f} | "
                     f"Spearman: {hourly_spearman:.4f} | "
                     f"Daily Pearson: {daily_pearson:.4f} ({strength})",
                     fontsize=17, fontweight='bold', y=0.97)

        # (charts 1-4 unchanged ...)
        norm = prices / prices.iloc[0] * 100
        norm.plot(ax=axs[0], linewidth=2.3)
        axs[0].set_title("1. Normalized Prices (100 at start of overlap)")
        axs[0].set_ylabel("Indexed Price")
        axs[0].legend(fontsize=12)

        x = daily_logret[self.sym1]
        y = daily_logret[self.sym2]
        sns.regplot(x=x, y=y, ax=axs[1],
                    scatter_kws={'alpha': 0.6, 's': 18, 'color': '#1f77b4'},
                    line_kws={'color': 'red', 'linewidth': 2.8})
        axs[1].text(0.02, 0.96,
                    f"Hourly Pearson (log returns) : {hourly_pearson:.4f}\n"
                    f"Hourly Spearman (rank)      : {hourly_spearman:.4f}\n"
                    f"Daily Pearson (log returns) : {daily_pearson:.4f}  ({strength})",
                    transform=axs[1].transAxes,
                    fontsize=13, fontweight='bold',
                    verticalalignment='top',
                    bbox=dict(boxstyle="round,pad=0.7", facecolor="yellow",
                              alpha=0.92, edgecolor="red", linewidth=2.2))
        axs[1].set_title("2. Daily Log Returns Scatter + Regression Line")
        axs[1].set_xlabel(f"{self.sym1} Daily Log Return")
        axs[1].set_ylabel(f"{self.sym2} Daily Log Return")

        window = 30
        rolling = daily_logret[self.sym1].rolling(window=window).corr(daily_logret[self.sym2])
        rolling.plot(ax=axs[2], color='purple', linewidth=2.8)
        axs[2].axhline(0.8, color='darkgreen', linestyle='--', alpha=0.8, label='Very Strong')
        axs[2].axhline(0.5, color='orange', linestyle='--', alpha=0.8, label='Moderate')
        axs[2].axhline(0.0, color='gray', linestyle='--', alpha=0.6)
        axs[2].set_title(f"3. {window}-Day Rolling Pearson Correlation")
        axs[2].set_ylabel("Correlation")
        axs[2].legend()

        ratio = prices[self.sym1] / prices[self.sym2]
        ratio.plot(ax=axs[3], color='teal', linewidth=2.2)
        mean_r = ratio.mean()
        axs[3].axhline(mean_r, color='red', linestyle='--', alpha=0.85,
                      label=f'Mean Ratio = {mean_r:.4f}')
        axs[3].set_title("4. Price Ratio (SYMBOL1 / SYMBOL2)")
        axs[3].set_ylabel("Ratio")
        axs[3].legend()

        plt.tight_layout(rect=[0, 0.02, 1, 0.96])

        filename = f"correlation_{self.sym1}_vs_{self.sym2}_{self.max_months}m.png"   # ← now includes months
        plt.savefig(filename, bbox_inches='tight', facecolor='white')
        print(f"\n✅ Saved: {filename}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(f"No symbols given — defaulting to ETH vs BTC (last 12 months)\n")
        sym1 = "ETH"
        sym2 = "BTC"
        file_path = "top100_hourly_1year_combined.csv"
        max_months = 12
    else:
        args = sys.argv[1:]
        max_months = 12
        if args and args[-1].isdigit():
            max_months = int(args.pop())

        if len(args) == 0:
            print(f"No symbols given — defaulting to ETH vs BTC (last {max_months} months)\n")
            sym1 = "ETH"
            sym2 = "BTC"
            file_path = "top100_hourly_1year_combined.csv"
        elif len(args) == 1:
            print("Usage: python draw_correlation_chart.py <symbol1> <symbol2> [csv_file] [max_months]")
            print("Example: python draw_correlation_chart.py ETH SOL 6")
            sys.exit(1)
        elif len(args) == 2:
            sym1 = args[0].upper()
            sym2 = args[1].upper()
            file_path = "top100_hourly_1year_combined.csv"
        elif len(args) == 3:
            sym1 = args[0].upper()
            sym2 = args[1].upper()
            file_path = args[2]
        else:
            print("Usage: python draw_correlation_chart.py <symbol1> <symbol2> [csv_file] [max_months]")
            sys.exit(1)

    drawer = CorrelationChartDrawer(sym1, sym2, file_path, max_months)
    drawer.draw()
