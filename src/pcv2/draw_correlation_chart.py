import matplotlib.pyplot as plt
import seaborn as sns
import sys
from get_correlation import CorrelationAnalyzer

# Nice dark theme for crypto charts
sns.set_style("darkgrid")
plt.rcParams.update({'figure.dpi': 160, 'font.size': 11})

class CorrelationChartDrawer:
    """Draws the 4 brutally simple + insightful correlation charts vertically."""

    def __init__(self, sym1: str, sym2: str, file_path: str = "top100_hourly_1year_combined.csv"):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.file_path = file_path

    def draw(self):
        # Run original analyzer (prints all text stats + computes everything)
        analyzer = CorrelationAnalyzer(self.sym1, self.sym2, self.file_path)
        analyzer.run()

        # Safety check (uses the data we exposed)
        if not hasattr(analyzer, 'prices') or len(analyzer.prices) < 200:
            print("⚠️  Not enough overlapping data for meaningful charts.")
            return

        prices = analyzer.prices
        daily_logret = analyzer.daily_logret

        # === One tall vertical figure with all 4 charts ===
        fig, axs = plt.subplots(4, 1, figsize=(13, 24), dpi=160)
        fig.suptitle(f"{self.sym1} vs {self.sym2} — Full Correlation Analysis\n"
                     f"(Overlap: {len(prices):,} hourly points)", 
                     fontsize=18, fontweight='bold', y=0.98)

        # 1. Normalized Price Overlay (the trader intuition chart)
        norm = prices / prices.iloc[0] * 100
        norm.plot(ax=axs[0], linewidth=2.3)
        axs[0].set_title("1. Normalized Prices (100 at start of overlap)")
        axs[0].set_ylabel("Indexed Price")
        axs[0].legend(fontsize=12)

        # 2. Log Returns Scatter + Regression (statistical truth)
        x = daily_logret[self.sym1]
        y = daily_logret[self.sym2]
        sns.regplot(x=x, y=y, ax=axs[1],
                    scatter_kws={'alpha': 0.6, 's': 18, 'color': '#1f77b4'},
                    line_kws={'color': 'red', 'linewidth': 2.8})
        axs[1].set_title("2. Daily Log Returns Scatter + Regression Line")
        axs[1].set_xlabel(f"{self.sym1} Daily Log Return")
        axs[1].set_ylabel(f"{self.sym2} Daily Log Return")

        # 3. Rolling Correlation (the "is this real?" chart)
        window = 30
        rolling = daily_logret[self.sym1].rolling(window=window).corr(daily_logret[self.sym2])
        rolling.plot(ax=axs[2], color='purple', linewidth=2.8)
        axs[2].axhline(0.8, color='darkgreen', linestyle='--', alpha=0.8, label='Very Strong')
        axs[2].axhline(0.5, color='orange', linestyle='--', alpha=0.8, label='Moderate')
        axs[2].axhline(0.0, color='gray', linestyle='--', alpha=0.6)
        axs[2].set_title(f"3. {window}-Day Rolling Pearson Correlation")
        axs[2].set_ylabel("Correlation")
        axs[2].legend()

        # 4. Price Ratio (pairs-trading / structural shift detector)
        ratio = prices[self.sym1] / prices[self.sym2]
        ratio.plot(ax=axs[3], color='teal', linewidth=2.2)
        mean_r = ratio.mean()
        axs[3].axhline(mean_r, color='red', linestyle='--', alpha=0.85,
                      label=f'Mean Ratio = {mean_r:.4f}')
        axs[3].set_title("4. Price Ratio (SYMBOL1 / SYMBOL2)")
        axs[3].set_ylabel("Ratio")
        axs[3].legend()

        plt.tight_layout(rect=[0, 0.02, 1, 0.96])

        # Save & show
        filename = f"correlation_{self.sym1}_vs_{self.sym2}.png"
        plt.savefig(filename, bbox_inches='tight', facecolor='white')
        print(f"\n✅ Saved: {filename}  (open it — all 4 charts vertically stacked)")
        plt.show()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("No symbols given — defaulting to ETH vs BTC\n")
        sym1 = "ETH"
        sym2 = "BTC"
    else:
        sym1 = sys.argv[1]
        sym2 = sys.argv[2]

    file_path = sys.argv[3] if len(sys.argv) > 3 else "top100_hourly_1year_combined.csv"

    drawer = CorrelationChartDrawer(sym1, sym2, file_path)
    drawer.draw()
