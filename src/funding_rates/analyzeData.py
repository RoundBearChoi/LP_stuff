import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats
import seaborn as sns
import sys

class BTCETHFundingAnalyzer:
    def __init__(self, csv_path='btc_eth_funding_spread_2y.csv', ratio_quantile=0.90):
        print("🔄 Loading BTC-ETH funding spread data...")
        self.df = pd.read_csv(csv_path, parse_dates=['open_time'])
        self.df.set_index('open_time', inplace=True)
        self.df.sort_index(inplace=True)

        self.abs_spread = np.abs(self.df['funding_spread'])

        # Dynamic large-spread threshold (top 5% of all historical |spreads|)
        self.large_spread_threshold = self.df['funding_spread'].abs().quantile(0.95)

        # User-configurable ratio quantile (default 0.90 = top 10%)
        self.ratio_quantile = ratio_quantile
        print(f"📊 Using top {int(self.ratio_quantile * 100)}% for large BTC/ETH ratio moves "
              f"(quantile = {self.ratio_quantile})")

    def _basic_stats(self):
        print("=== BASIC STATS ===")
        print(self.df[['btc_close', 'eth_close', 'btc_funding', 'eth_funding', 'funding_spread']].describe())

        print("\n=== FUNDING DIRECTIONAL SKEW ===")
        print(f"BTC funding positive: {(self.df['btc_funding'] > 0).mean():.1%}")
        print(f"ETH funding positive: {(self.df['eth_funding'] > 0).mean():.1%}")
        print(f"Spread positive (BTC > ETH): {(self.df['funding_spread'] > 0).mean():.1%}")
        print(f"Spread skewness: {stats.skew(self.df['funding_spread']):.3f}")

        print(f"\n=== LARGE FUNDING SPREAD THRESHOLD (dynamic) ===")
        print(f"Top 5% largest |spread| threshold: {self.large_spread_threshold:.6f}")

    def _main_png(self):
        fig_main = plt.figure(figsize=(16, 22), constrained_layout=True)

        ax1 = fig_main.add_subplot(4, 1, 1)
        ax1.plot(self.df.index, self.df['btc_close'], label='BTC Close', color='orange', lw=1.5)
        ax1_twin = ax1.twinx()
        ax1_twin.plot(self.df.index, self.df['eth_close'], label='ETH Close', color='blue', lw=1.5)
        ax1.set_ylabel('BTC Price (USD)', color='orange')
        ax1_twin.set_ylabel('ETH Price (USD)', color='blue')
        ax1.legend(loc='upper left')
        ax1_twin.legend(loc='upper right')
        ax1.set_title('BTC & ETH Prices')

        ax2 = fig_main.add_subplot(4, 1, 2)
        ax2.plot(self.df.index, self.df['btc_funding'], label='BTC Funding', color='orange')
        ax2.plot(self.df.index, self.df['eth_funding'], label='ETH Funding', color='blue')
        ax2.axhline(0, color='gray', ls='--', lw=0.8)
        ax2.set_ylabel('Funding Rate')
        ax2.legend()
        ax2.set_title('BTC vs ETH Funding Rates (positive = bullish skew)')

        ax3 = fig_main.add_subplot(4, 1, 3)
        sc = ax3.scatter(self.df.index, self.df['funding_spread'],
                         c=self.abs_spread, cmap='RdYlGn_r', s=3, alpha=0.7)
        ax3.axhline(0, color='gray', ls='--', lw=0.8)
        ax3.set_ylabel('Funding Spread (BTC - ETH)')
        fig_main.colorbar(sc, ax=ax3, label='|Spread| → Skew Magnitude (Green=small/balanced • Red=large skew)')
        ax3.set_title('Funding Spread + Skew Strength')

        ax4 = fig_main.add_subplot(4, 1, 4)
        monthly = self.df['funding_spread'].resample('ME').mean()
        monthly_abs = np.abs(monthly)
        colors = plt.cm.RdYlGn_r(monthly_abs / monthly_abs.max())
        ax4.bar(monthly.index, monthly, color=colors, width=20)
        ax4.axhline(0, color='gray', ls='--')
        ax4.set_title('Monthly Average Funding Spread (Green=small skew • Red=large skew)')
        ax4.set_ylabel('Avg Spread')
        ax4.tick_params(axis='x', rotation=45)

        fig_main.suptitle(f'BTC-ETH Funding Main Analysis\n{self.df.index[0].date()} — {self.df.index[-1].date()}', 
                          fontsize=18, fontweight='bold', y=0.98)

        plt.savefig('btc_eth_funding_main.png', dpi=180, bbox_inches='tight', facecolor='white')
        plt.close()

    def _extra_png(self):
        fig_extra = plt.figure(figsize=(16, 9), constrained_layout=True)

        ax5 = fig_extra.add_subplot(1, 2, 1)
        sns.histplot(self.df['funding_spread'], bins=100, kde=True, color='purple', ax=ax5)
        ax5.axvline(0, color='gray', ls='--')
        ax5.set_title('Distribution of Funding Spread')
        ax5.set_xlabel('Funding Spread')

        ax6 = fig_extra.add_subplot(1, 2, 2)
        sc2 = ax6.scatter(self.df['btc_eth_ratio'], self.df['funding_spread'],
                          c=self.abs_spread, cmap='RdYlGn_r', alpha=0.6, s=4)
        fig_extra.colorbar(sc2, ax=ax6, label='|Spread| Skew Magnitude')
        ax6.axhline(0, color='gray', ls='--')
        ax6.set_xlabel('BTC/ETH Price Ratio')
        ax6.set_ylabel('Funding Spread')
        ax6.set_title('BTC/ETH Ratio vs Funding Spread')

        fig_extra.suptitle(f'BTC-ETH Funding Extra Charts\n{self.df.index[0].date()} — {self.df.index[-1].date()}', 
                           fontsize=16, fontweight='bold')

        plt.savefig('btc_eth_funding_extra.png', dpi=200, bbox_inches='tight', facecolor='white')
        plt.close()

    def _ratio_change(self):
        self.df['ratio_24h_change'] = self.df['btc_eth_ratio'].shift(-96) - self.df['btc_eth_ratio']

    def _large_spread_chart(self):
        plt.figure(figsize=(12, 8))
        plt.scatter(self.df['funding_spread'], self.df['ratio_24h_change'],
                    c='lightgray', s=3, alpha=0.4, label='All data (small spread)')

        large_mask = self.abs_spread > self.large_spread_threshold
        sc3 = plt.scatter(self.df.loc[large_mask, 'funding_spread'], 
                          self.df.loc[large_mask, 'ratio_24h_change'],
                          c=self.abs_spread[large_mask], cmap='RdYlGn_r', s=20, alpha=0.95, 
                          edgecolor='black', linewidth=0.5, 
                          label=f'Large spread (>{self.large_spread_threshold:.6f})')

        plt.colorbar(sc3, label='|Current Spread| → Skew Magnitude (Large spreads only)')
        plt.axhline(0, color='gray', ls='--', lw=1)
        plt.axvline(0, color='gray', ls='--', lw=1)
        plt.xlabel('Current Funding Spread (BTC - ETH)')
        plt.ylabel('BTC/ETH Ratio Change over Next 24h')
        plt.title('Large Funding Spreads Highlighted vs Future BTC/ETH Ratio Move')
        plt.legend()
        plt.savefig('btc_eth_spread_vs_future_ratio.png', dpi=180, bbox_inches='tight')
        plt.close()

    def _large_ratio_moves(self):
        large_ratio_threshold = self.df['ratio_24h_change'].abs().quantile(self.ratio_quantile)
        self.df['large_ratio_move'] = self.df['ratio_24h_change'].abs() > large_ratio_threshold

        print(f"\n=== PREDICTING LARGE BTC/ETH RATIO MOVES (top {int(self.ratio_quantile * 100)}% magnitude) ===")
        print(f"Large move threshold (|24h ratio change|): {large_ratio_threshold:.4f}")

        baseline = self.df['large_ratio_move'].mean()
        when_large_spread = self.df[self.abs_spread > self.large_spread_threshold]['large_ratio_move'].mean()

        print(f"Baseline probability of large move: {baseline:.1%}")
        print(f"When |spread| > {self.large_spread_threshold:.6f} → probability of large move: {when_large_spread:.1%}")
        print(f"Lift: {when_large_spread / baseline:.2f}x more likely")

        plt.figure(figsize=(12, 8))
        plt.scatter(self.df['funding_spread'], self.df['ratio_24h_change'],
                    c='lightgray', s=3, alpha=0.4)

        large_move_mask = self.df['large_ratio_move']
        plt.scatter(self.df.loc[large_move_mask, 'funding_spread'], 
                    self.df.loc[large_move_mask, 'ratio_24h_change'],
                    c='red', s=25, alpha=0.9, edgecolor='black', linewidth=0.5, 
                    label=f'Large ratio move (|Δ| > {large_ratio_threshold:.4f})')

        plt.axhline(0, color='gray', ls='--', lw=1)
        plt.axvline(0, color='gray', ls='--', lw=1)
        plt.xlabel('Current Funding Spread (BTC - ETH)')
        plt.ylabel('BTC/ETH Ratio Change over Next 24h')
        plt.title('Large BTC/ETH Ratio Moves Highlighted')
        plt.legend()
        plt.savefig('btc_eth_large_ratio_moves.png', dpi=180, bbox_inches='tight')
        plt.close()

        self.df['funding_spread_abs'] = self.abs_spread
        big_div = self.df.nlargest(10, 'funding_spread_abs')
        print("\nTop 10 largest funding spreads and 24h BTC/ETH ratio change afterward:")
        print(big_div[['funding_spread', 'ratio_24h_change']].round(6))

    def _fourteen_day_kst_chart(self):
        print("\nGenerating Simple 14D Funding Spread Chart (KST + dynamic large-spread lines)...")

        end_time = self.df.index.max()
        start_time = end_time - pd.Timedelta(days=14)
        recent_df = self.df[(self.df.index >= start_time) & (self.df.index <= end_time)].copy()

        recent_df = recent_df.copy()
        recent_df.index = recent_df.index.tz_localize('UTC').tz_convert('Asia/Seoul')

        if len(recent_df) < 20:
            print("   Warning: Less than 14d of data — using last 1400 points as fallback")
            recent_df = self.df.tail(1400).copy()
            recent_df.index = recent_df.index.tz_localize('UTC').tz_convert('Asia/Seoul')

        fig, ax = plt.subplots(figsize=(15, 8.5))

        spread_scaled = recent_df['funding_spread'] * 1_000_000

        ax.plot(recent_df.index, spread_scaled, 
                color='purple', lw=3.5, marker='o', markersize=3.5, 
                label='BTC-ETH Funding Spread (Delta)')

        ax.axhline(0, color='black', ls='--', lw=1.5)

        large_spread_scaled = self.large_spread_threshold * 1_000_000
        ax.axhline(large_spread_scaled, color='red', ls='--', lw=1.8, alpha=0.85, 
                   label=f'Large Spread Threshold (±{self.large_spread_threshold:.6f})')
        ax.axhline(-large_spread_scaled, color='red', ls='--', lw=1.8, alpha=0.85)

        data_min = spread_scaled.min()
        data_max = spread_scaled.max()
        data_range = max(data_max - data_min, 1.0)
        padding = 0.25 * data_range
        ax.set_ylim(min(data_min - padding, -large_spread_scaled*1.15), 
                    max(data_max + padding, large_spread_scaled*1.15))

        current_spread = recent_df['funding_spread'].iloc[-1]
        current_scaled = current_spread * 1_000_000

        ax.annotate(f'CURRENT SPREAD\n{current_spread:+.8f}\n({current_scaled:+.2f} ×10⁻⁶)', 
                    xy=(recent_df.index[-1], current_scaled),
                    xytext=(35, 45 if current_spread >= 0 else -70),
                    textcoords='offset points',
                    fontsize=15, fontweight='bold', ha='left',
                    bbox=dict(boxstyle="round,pad=0.8", facecolor='yellow', alpha=0.95))

        ax.set_title('BTC - ETH Funding Rate Difference (Last 14 Days)', fontsize=18, fontweight='bold', pad=20)
        ax.set_ylabel('Spread × 1,000,000', fontsize=14)
        ax.set_xlabel('Time (KST)')
        ax.legend(fontsize=11, loc='upper right')
        ax.grid(True, alpha=0.35)

        fig.suptitle(f'Latest data: {recent_df.index[-1].strftime("%Y-%m-%d %H:%M KST")}', 
                     fontsize=13, y=0.97)

        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('btc_eth_funding_14d_delta.png', dpi=260, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"   • btc_eth_funding_14d_delta.png  (KST + dynamic ±{self.large_spread_threshold:.6f} lines | Current: {current_spread:+.8f})")

    def run(self):
        self._basic_stats()
        self._main_png()
        self._extra_png()
        self._ratio_change()
        self._large_spread_chart()
        self._large_ratio_moves()
        self._fourteen_day_kst_chart()

        print("\n✅ ALL DONE! Files saved:")
        print("   • btc_eth_funding_main.png")
        print("   • btc_eth_funding_extra.png")
        print("   • btc_eth_spread_vs_future_ratio.png")
        print("   • btc_eth_large_ratio_moves.png")
        print("   • btc_eth_funding_14d_delta.png")


# ====================== RUN THE ANALYSIS ======================
if __name__ == "__main__":
    # Default = top 10% (quantile 0.90)
    ratio_quantile = 0.90

    if len(sys.argv) > 1:
        try:
            q = int(sys.argv[1])
            if 1 <= q <= 99:
                ratio_quantile = q / 100.0
            else:
                print(f"⚠️  Quantile {q} out of valid range (1-99). Using default 90.")
        except ValueError:
            print("⚠️  Invalid argument. Usage: python analyzeData.py [80|90|95|99]")
            print("   Using default 90.")

    analyzer = BTCETHFundingAnalyzer(ratio_quantile=ratio_quantile)
    analyzer.run()
