import sys
import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

sns.set_style("darkgrid")
plt.rcParams['figure.figsize'] = (15, 12.2)   # Taller figure for header space

class PriceAnalyzer:
    def __init__(self, token1: str, token2: str):
        self.name1 = token1.upper()
        self.name2 = token2.upper()
        self.filename = f"{self.name1}_{self.name2}_daily_closing_prices_2y.csv"

    def load_data(self):
        if not os.path.exists(self.filename):
            print(f"❌ CSV not found: {self.filename}")
            print("   First run: python getPrices.py btc eth")
            sys.exit(1)
        
        df = pd.read_csv(self.filename, index_col='Date', parse_dates=True)
        self.df = df[[self.name1, self.name2]].dropna()
        print(f"✅ Loaded {len(self.df):,} days from {self.df.index[0].date()} to {self.df.index[-1].date()}")

    def analyze_and_plot(self):
        df = self.df.copy()
        col1, col2 = self.name1, self.name2

        # Calculate the 3 key metrics
        df['Ret1'] = np.log(df[col1] / df[col1].shift(1))
        df['Ret2'] = np.log(df[col2] / df[col2].shift(1))
        df = df.dropna()

        corr = df['Ret1'].corr(df['Ret2'])

        # Cointegration
        coint_score, pvalue, crit_values = coint(df[col1], df[col2], trend='c', method='aeg')

        # Hedge ratio & Spread for half-life
        log_col2 = np.log(df[col2])
        X = sm.add_constant(log_col2)
        model = sm.OLS(np.log(df[col1]), X).fit()
        beta = model.params.iloc[-1]

        spread = np.log(df[col1]) - beta * np.log(df[col2])
        spread_lag = spread.shift(1)
        delta_spread = spread - spread_lag
        reg = sm.OLS(delta_spread.dropna(), sm.add_constant(spread_lag.dropna())).fit()
        hl_lambda = reg.params.iloc[-1]
        half_life = -np.log(2) / hl_lambda if hl_lambda < 0 else np.nan

        # ====================== 3 KEY METRICS (console) ======================
        print("\n" + "="*80)
        print(f"📊 3 KEY METRICS: {col1} vs {col2}  (for Liquidity Pool)")
        print("="*80)

        print("1. Cointegration p-value ← #1 by far (want < 0.05, ideally < 0.01)")
        print(f"   Cointegration p-value : {pvalue:.4f}\n")

        print("2. Half-life ← how fast the ratio snaps back (want 10–60 days)")
        print(f"   Half-life             : {half_life:.1f} days\n" if not np.isnan(half_life) else "   Half-life             : No mean reversion detected\n")

        print("3. Daily return correlation ← helpful but secondary")
        print(f"   Daily correlation     : {corr:.4f}")

        print("="*80)

        # ====================== CHARTS ======================
        fig = plt.figure()

        ax1 = fig.add_subplot(2, 3, 1)
        (df[[col1, col2]] / df[[col1, col2]].iloc[0] * 100).plot(ax=ax1)
        ax1.set_title('Normalized Prices')

        ax2 = fig.add_subplot(2, 3, 2)
        (df[col1] / df[col2]).plot(ax=ax2, color='purple')
        ax2.set_title(f'{col1}/{col2} Price Ratio')

        ax3 = fig.add_subplot(2, 3, 3)
        df['Ret1'].rolling(60).corr(df['Ret2']).plot(ax=ax3, color='orange')
        ax3.axhline(corr, color='red', linestyle='--')
        ax3.set_title('60-day Rolling Correlation')

        ax4 = fig.add_subplot(2, 3, 4)
        sns.regplot(x=df['Ret2'], y=df['Ret1'], scatter_kws={'alpha':0.5}, line_kws={'color':'red'}, ax=ax4)
        ax4.set_title('Daily Returns Scatter')

        ax5 = fig.add_subplot(2, 3, 5)
        spread.plot(ax=ax5, color='teal')
        ax5.axhline(spread.mean(), color='black', linestyle='--')
        ax5.set_title('Cointegrating Spread')

        ax6 = fig.add_subplot(2, 3, 6)
        zscore = (spread - spread.mean()) / spread.std()
        zscore.plot(ax=ax6, color='darkred')
        ax6.axhline(0, color='black', linestyle='--')
        ax6.axhline(2, color='red', linestyle=':')
        ax6.axhline(-2, color='green', linestyle=':')
        ax6.set_title('Z-Score')

        plt.suptitle(f'{col1} vs {col2} — 3 Key Metrics for LP', fontsize=16.5, y=0.96)

        # ====================== 3 KEY METRICS ON THE PNG ======================
        hl_str = f"{half_life:.1f} days" if not np.isnan(half_life) else "No mean reversion detected"

        metrics_text = f"""                  3 KEY METRICS
────────────────────────────────────
   Cointegration p-value : {pvalue:.4f}
   Half-life             : {hl_str}
   Daily correlation     : {corr:.4f}"""

        fig.text(0.5, 0.915, metrics_text,
                 ha='center', va='top', fontsize=12,
                 fontfamily='monospace', linespacing=1.7,
                 bbox=dict(boxstyle='round,pad=1.1', facecolor='#e3f2fd',
                           edgecolor='#1976d2', linewidth=2))

        # Generous top space so nothing gets hidden
        plt.tight_layout(rect=[0.02, 0.02, 0.98, 0.80])

        plot_file = f"{col1}_{col2}_LP_analysis.png"
        plt.savefig(plot_file, dpi=160, bbox_inches='tight')
        print(f"\n💾 Charts saved → {plot_file}")

        # Save full data
        df['Spread'] = spread
        df['Spread_Zscore'] = zscore
        df.to_csv(f"{col1}_{col2}_full_analysis.csv")
        print(f"💾 Full data saved → {col1}_{col2}_full_analysis.csv")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python analyzePrices.py <token1> <token2>")
        print("Example: python analyzePrices.py sol fart")
        sys.exit(1)

    analyzer = PriceAnalyzer(sys.argv[1], sys.argv[2])
    analyzer.load_data()
    analyzer.analyze_and_plot()
