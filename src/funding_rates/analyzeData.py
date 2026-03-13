import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
import seaborn as sns
import sys

class PairFundingAnalyzer:
    def __init__(self, ratio_quantile=0.90):
        if len(sys.argv) < 3:
            print("Usage: python analyzeData.py <symbol1> <symbol2> [quantile]")
            print("Example: python analyzeData.py cake btc")
            print("         python analyzeData.py cake btc 95")
            sys.exit(1)
        
        self.sym1 = sys.argv[1].upper()
        self.sym2 = sys.argv[2].upper()
        self.s1 = self.sym1.lower()
        self.s2 = self.sym2.lower()
        
        csv_path = f'{self.s1}_{self.s2}_funding_spread_2y.csv'
        print(f"🔄 Loading {self.sym1}-{self.sym2} funding spread data...")
        self.df = pd.read_csv(csv_path, parse_dates=['open_time'])
        self.df.set_index('open_time', inplace=True)
        self.df.sort_index(inplace=True)

        self.col_close1 = f'{self.s1}_close'
        self.col_close2 = f'{self.s2}_close'
        self.col_fund1  = f'{self.s1}_funding'
        self.col_fund2  = f'{self.s2}_funding'
        self.ratio_col  = f'{self.s1}_{self.s2}_ratio'

        self.abs_spread = np.abs(self.df['funding_spread'])
        self.large_spread_threshold = self.df['funding_spread'].abs().quantile(0.95)
        
        if len(sys.argv) > 3:
            try:
                q = int(sys.argv[3])
                if 1 <= q <= 99:
                    self.ratio_quantile = q / 100.0
            except:
                self.ratio_quantile = ratio_quantile
        else:
            self.ratio_quantile = ratio_quantile
        print(f"📊 Using top {int(self.ratio_quantile * 100)}% for large {self.sym1}/{self.sym2} ratio moves")

    def _basic_stats(self):
        print("=== BASIC STATS ===")
        print(self.df[[self.col_close1, self.col_close2, self.col_fund1, self.col_fund2, 'funding_spread']].describe())

        print("\n=== FUNDING DIRECTIONAL SKEW ===")
        print(f"{self.sym1} funding positive: {(self.df[self.col_fund1] > 0).mean():.1%}")
        print(f"{self.sym2} funding positive: {(self.df[self.col_fund2] > 0).mean():.1%}")
        print(f"Spread positive ({self.sym1} > {self.sym2}): {(self.df['funding_spread'] > 0).mean():.1%}")
        print(f"Spread skewness: {stats.skew(self.df['funding_spread']):.3f}")

        print(f"\n=== LARGE FUNDING SPREAD THRESHOLD ===")
        print(f"Top 5% largest |spread| threshold: {self.large_spread_threshold:.6f}")

    def _main_png(self):
        fig_main = plt.figure(figsize=(16, 22), constrained_layout=True)
        ax1 = fig_main.add_subplot(4, 1, 1)
        ax1.plot(self.df.index, self.df[self.col_close1], label=f'{self.sym1} Close', color='orange', lw=1.5)
        ax1_twin = ax1.twinx()
        ax1_twin.plot(self.df.index, self.df[self.col_close2], label=f'{self.sym2} Close', color='blue', lw=1.5)
        ax1.set_ylabel(f'{self.sym1} Price (USD)', color='orange')
        ax1_twin.set_ylabel(f'{self.sym2} Price (USD)', color='blue')
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')
        ax1.set_title(f'{self.sym1} & {self.sym2} Prices')

        ax2 = fig_main.add_subplot(4, 1, 2)
        ax2.plot(self.df.index, self.df[self.col_fund1], label=f'{self.sym1} Funding', color='orange')
        ax2.plot(self.df.index, self.df[self.col_fund2], label=f'{self.sym2} Funding', color='blue')
        ax2.axhline(0, color='gray', ls='--', lw=0.8)
        ax2.set_ylabel('Funding Rate')
        ax2.legend()
        ax2.set_title(f'{self.sym1} vs {self.sym2} Funding Rates (positive = bullish skew)')

        ax3 = fig_main.add_subplot(4, 1, 3)
        sc = ax3.scatter(self.df.index, self.df['funding_spread'], c=self.abs_spread, cmap='RdYlGn_r', s=3, alpha=0.7)
        ax3.axhline(0, color='gray', ls='--', lw=0.8)
        ax3.set_ylabel('Funding Spread')
        fig_main.colorbar(sc, ax=ax3, label='|Spread| → Skew Magnitude')
        ax3.set_title('Funding Spread + Skew Strength')

        ax4 = fig_main.add_subplot(4, 1, 4)
        monthly = self.df['funding_spread'].resample('ME').mean()
        monthly_abs = np.abs(monthly)
        colors = plt.cm.RdYlGn_r(monthly_abs / monthly_abs.max())
        ax4.bar(monthly.index, monthly, color=colors, width=20)
        ax4.axhline(0, color='gray', ls='--')
        ax4.set_title('Monthly Average Funding Spread')
        ax4.set_ylabel('Avg Spread')
        ax4.tick_params(axis='x', rotation=45)

        fig_main.suptitle(f'{self.sym1}-{self.sym2} Funding Main Analysis\n{self.df.index[0].date()} — {self.df.index[-1].date()}', fontsize=18, fontweight='bold', y=0.98)
        plt.savefig(f'{self.s1}_{self.s2}_funding_main.png', dpi=180, bbox_inches='tight', facecolor='white')
        plt.close()

    def _extra_png(self):
        fig_extra = plt.figure(figsize=(16, 9), constrained_layout=True)
        ax5 = fig_extra.add_subplot(1, 2, 1)
        sns.histplot(self.df['funding_spread'], bins=100, kde=True, color='purple', ax=ax5)
        ax5.axvline(0, color='gray', ls='--')
        ax5.set_title('Distribution of Funding Spread')
        ax5.set_xlabel('Funding Spread')

        ax6 = fig_extra.add_subplot(1, 2, 2)
        sc2 = ax6.scatter(self.df[self.ratio_col], self.df['funding_spread'], c=self.abs_spread, cmap='RdYlGn_r', alpha=0.6, s=4)
        fig_extra.colorbar(sc2, ax=ax6, label='|Spread| Skew Magnitude')
        ax6.axhline(0, color='gray', ls='--')
        ax6.set_xlabel(f'{self.sym1}/{self.sym2} Price Ratio')
        ax6.set_ylabel('Funding Spread')
        ax6.set_title(f'{self.sym1}/{self.sym2} Ratio vs Funding Spread')

        fig_extra.suptitle(f'{self.sym1}-{self.sym2} Funding Extra Charts\n{self.df.index[0].date()} — {self.df.index[-1].date()}', fontsize=16, fontweight='bold')
        plt.savefig(f'{self.s1}_{self.s2}_funding_extra.png', dpi=200, bbox_inches='tight', facecolor='white')
        plt.close()

    def _ratio_change(self):
        self.df['ratio_24h_change'] = self.df[self.ratio_col].shift(-96) - self.df[self.ratio_col]

    def _large_spread_chart(self):
        plt.figure(figsize=(12, 8))
        large_mask = self.abs_spread > self.large_spread_threshold
        sc3 = plt.scatter(self.df.loc[large_mask, 'funding_spread'], 
                          self.df.loc[large_mask, 'ratio_24h_change'],
                          c=self.abs_spread[large_mask], cmap='RdYlGn_r', s=20, alpha=0.95, edgecolor='black', linewidth=0.5)
        plt.axhline(0, color='gray', ls='--', lw=1)
        plt.axvline(0, color='gray', ls='--', lw=1)
        plt.xlabel('Current Funding Spread')
        plt.ylabel(f'{self.sym1}/{self.sym2} Ratio Change over Next 24h')
        plt.title('Large Funding Spreads vs Future Ratio Move')
        plt.savefig(f'{self.s1}_{self.s2}_spread_vs_future_ratio.png', dpi=180, bbox_inches='tight')
        plt.close()

    def _large_ratio_moves(self):
        large_ratio_threshold = self.df['ratio_24h_change'].abs().quantile(self.ratio_quantile)
        self.df['large_ratio_move'] = self.df['ratio_24h_change'].abs() > large_ratio_threshold

        print(f"\n=== PREDICTING LARGE {self.sym1}/{self.sym2} RATIO MOVES ===")
        print(f"Large move threshold: {large_ratio_threshold:.4f}")
        baseline = self.df['large_ratio_move'].mean()
        when_large = self.df[self.abs_spread > self.large_spread_threshold]['large_ratio_move'].mean()
        print(f"Baseline prob: {baseline:.1%}")
        print(f"When |spread| large → {when_large:.1%} (lift: {when_large / baseline:.2f}x)")

        big_div = self.df.nlargest(10, 'funding_spread'.replace('funding_spread', 'abs_spread' if False else 'funding_spread_abs' if 'funding_spread_abs' in self.df else 'funding_spread'))
        print("\nTop 10 largest spreads and 24h ratio change:")
        print(big_div[['funding_spread', 'ratio_24h_change']].round(6))

    def _fourteen_day_kst_chart(self):
        print("\nGenerating 14D Funding Spread Chart (KST)...")
        end_time = self.df.index.max()
        start_time = end_time - pd.Timedelta(days=14)
        recent_df = self.df[(self.df.index >= start_time)].copy()
        recent_df.index = recent_df.index.tz_localize('UTC').tz_convert('Asia/Seoul')

        fig, ax = plt.subplots(figsize=(15, 8.5))
        spread_scaled = recent_df['funding_spread'] * 1_000_000
        ax.plot(recent_df.index, spread_scaled, color='purple', lw=3.5, marker='o', markersize=3.5, label=f'{self.sym1}-{self.sym2} Spread')
        ax.axhline(0, color='black', ls='--', lw=1.5)
        large_scaled = self.large_spread_threshold * 1_000_000
        ax.axhline(large_scaled, color='red', ls='--', lw=1.8, label=f'Large ±{self.large_spread_threshold:.6f}')
        ax.axhline(-large_scaled, color='red', ls='--', lw=1.8)

        current = recent_df['funding_spread'].iloc[-1]
        ax.annotate(f'CURRENT\n{current:+.8f}', xy=(recent_df.index[-1], current*1_000_000), xytext=(35, 45 if current >= 0 else -70), textcoords='offset points', fontsize=15, fontweight='bold', bbox=dict(boxstyle="round,pad=0.8", facecolor='yellow', alpha=0.95))

        ax.set_title(f'{self.sym1} - {self.sym2} Funding Rate Difference (Last 14 Days)', fontsize=18, fontweight='bold')
        ax.set_ylabel('Spread × 1,000,000')
        ax.set_xlabel('Time (KST)')
        ax.legend()
        plt.savefig(f'{self.s1}_{self.s2}_funding_14d_delta.png', dpi=260, bbox_inches='tight', facecolor='white')
        plt.close()

    def run(self):
        self._basic_stats()
        self._main_png()
        self._extra_png()
        self._ratio_change()
        self._large_spread_chart()
        self._large_ratio_moves()
        self._fourteen_day_kst_chart()
        print(f"\n✅ ALL DONE for {self.sym1}-{self.sym2}!")
        print(f"   Charts saved with prefix '{self.s1}_{self.s2}_'")

if __name__ == "__main__":
    analyzer = PairFundingAnalyzer()
    analyzer.run()
