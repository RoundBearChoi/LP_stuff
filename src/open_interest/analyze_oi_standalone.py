import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys

class PairOIAnalyzerStandalone:
    def __init__(self, base="btc", quote="eth"):
        self.base = base.upper()
        self.quote = quote.upper()
        self.prefix = f"{base.lower()}_{quote.lower()}"
        self.csv_path = f"{self.prefix}_oi_standalone.csv"
        
        self.price_ratio_col = f"{base.lower()}_{quote.lower()}_price_ratio"
        self.oi_ratio_col = f"{base.lower()}_{quote.lower()}_oi_ratio"
        
        print(f"🔄 Loading standalone {self.base}-{self.quote} OI dataset...")
        self.df = pd.read_csv(self.csv_path, parse_dates=['open_time'])
        self.df.set_index('open_time', inplace=True)
        self.recent = self.df.dropna(subset=[self.oi_ratio_col]).copy()
        self.abs_oi_change = np.abs(self.recent['oi_ratio_24h_change'])
        self.large_oi_threshold = self.abs_oi_change.quantile(0.95)

    def _basic_stats(self):
        print("\n=== STANDALONE OI BASIC STATS ===")
        print(self.recent[[self.oi_ratio_col, self.price_ratio_col, 'oi_ratio_24h_change']].describe())
        print(f"\nCurrent {self.base}/{self.quote} OI Ratio (USD): {self.recent[self.oi_ratio_col].iloc[-1]:.3f}")
        print(f"Current {self.base}/{self.quote} Price Ratio:     {self.recent[self.price_ratio_col].iloc[-1]:.3f}")

    def _large_oi_vs_price_scatter(self):
        plt.figure(figsize=(12, 8))
        large_mask = self.abs_oi_change > self.large_oi_threshold
        plt.scatter(self.recent['oi_ratio_24h_change'], self.recent['price_ratio_24h_change'],
                    c='lightgray', s=5, alpha=0.4, label='All data')
        plt.scatter(self.recent.loc[large_mask, 'oi_ratio_24h_change'],
                    self.recent.loc[large_mask, 'price_ratio_24h_change'],
                    c='red', s=25, edgecolor='black', label=f'Large OI ratio move (top 5%)')
        plt.axhline(0, color='gray', ls='--')
        plt.axvline(0, color='gray', ls='--')
        plt.xlabel('Current 24h OI Ratio Change')
        plt.ylabel('Next 24h Price Ratio Change')
        plt.title(f'Large OI Ratio Moves vs Future {self.base}/{self.quote} Price Move')
        plt.legend()
        plt.savefig(f'{self.prefix}_large_oi_vs_price.png', dpi=160, bbox_inches='tight')
        plt.close()

    def _fourteen_day_dual_chart(self):
        print("\nGenerating 14-day stacked chart (KST)...")
        end_time = self.recent.index.max()
        start_time = end_time - pd.Timedelta(days=14)
        plot_df = self.recent[(self.recent.index >= start_time) & (self.recent.index <= end_time)].copy()
        plot_df.index = plot_df.index.tz_localize('UTC').tz_convert('Asia/Seoul')

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 9.5), sharex=True, gridspec_kw={'height_ratios': [1, 1]})

        ax1.plot(plot_df.index, plot_df[self.price_ratio_col], color='orange', lw=2.5, label=f'{self.base}/{self.quote} Price Ratio')
        ax1.set_ylabel('Price Ratio', color='orange')
        ax1.set_title(f'{self.base}/{self.quote} Price Ratio (Last 14 Days)', fontsize=14, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')

        ax2.plot(plot_df.index, plot_df[self.oi_ratio_col], color='teal', lw=3, label=f'{self.base}/{self.quote} OI Ratio (USD)')
        ax2.set_ylabel('OI Ratio (USD)', color='teal')
        ax2.set_title(f'{self.base}/{self.quote} OI Ratio (USD) (Last 14 Days)', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper left')

        current_oi = plot_df[self.oi_ratio_col].iloc[-1]
        ax2.annotate(f'CURRENT\nOI Ratio: {current_oi:.3f}',
                     xy=(plot_df.index[-1], current_oi),
                     xytext=(30, 40), textcoords='offset points', fontsize=14, fontweight='bold',
                     bbox=dict(boxstyle="round,pad=0.8", facecolor='yellow', alpha=0.95))

        fig.suptitle(f'{self.base}-{self.quote} OI vs Price Ratio (Last 14 Days) — Stacked for Clarity\nLatest: {plot_df.index[-1].strftime("%Y-%m-%d %H:%M KST")}', 
                     y=0.96, fontsize=18, fontweight='bold')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{self.prefix}_oi_14d_standalone.png', dpi=160, bbox_inches='tight', facecolor='white')
        plt.close()
        print(f"   • {self.prefix}_oi_14d_standalone.png  (stacked: Price on top • OI on bottom)")

    def _oi_spike_detector_chart(self):
        print("\nGenerating OI Spike/Drop Detector chart (last 60 days, KST)...")
        plt.figure(figsize=(15, 7.5))
        
        end_time = self.recent.index.max()
        start_time = end_time - pd.Timedelta(days=60)
        plot_df = self.recent[self.recent.index >= start_time].copy()
        plot_df = plot_df.dropna(subset=['oi_ratio_24h_change']).copy()
        plot_df.index = plot_df.index.tz_localize('UTC').tz_convert('Asia/Seoul')
        
        colors = []
        for val in plot_df['oi_ratio_24h_change']:
            if val > self.large_oi_threshold:
                colors.append('#d62728')
            elif val < -self.large_oi_threshold:
                colors.append('#1f77b4')
            else:
                colors.append('#7f7f7f')
        
        bars = plt.bar(plot_df.index, plot_df['oi_ratio_24h_change'], 
                       color=colors, alpha=0.85, width=0.85, zorder=2)
        
        plt.axhline(self.large_oi_threshold, color='red', linestyle='--', lw=2.5,
                   label=f'Spike Threshold (+{self.large_oi_threshold:.4f})')
        plt.axhline(-self.large_oi_threshold, color='blue', linestyle='--', lw=2.5,
                   label=f'Drop Threshold (-{self.large_oi_threshold:.4f})')
        plt.axhline(0, color='black', lw=1)
        
        latest_idx = -1
        latest_change = plot_df['oi_ratio_24h_change'].iloc[latest_idx]
        latest_time_str = plot_df.index[latest_idx].strftime("%Y-%m-%d %H:%M KST")
        latest_bar = bars[latest_idx]
        
        latest_bar.set_color('#ffeb3b')
        latest_bar.set_edgecolor('black')
        latest_bar.set_linewidth(4)
        latest_bar.set_zorder(5)
        
        if latest_change > self.large_oi_threshold:
            status = "STRONG SPIKE ↑"
        elif latest_change < -self.large_oi_threshold:
            status = "STRONG DROP ↓"
        else:
            status = "Normal"
        
        offset_y = 42 if latest_change >= 0 else -72
        plt.annotate(f'TODAY\n({latest_time_str})\n{latest_change:+.4f}\n{status}', 
                    xy=(plot_df.index[latest_idx], latest_change),
                    xytext=(15, offset_y),
                    textcoords='offset points',
                    fontsize=13,
                    fontweight='bold',
                    ha='left',
                    arrowprops=dict(arrowstyle='->', color='black', lw=1.8),
                    bbox=dict(boxstyle="round,pad=0.9", facecolor='yellow', alpha=0.98, edgecolor='orange'))
        
        plt.title(f'{self.base}/{self.quote} OI Ratio 24h Change — Spike / Drop Detector', 
                 fontsize=16, fontweight='bold')
        plt.ylabel('24h Change in OI Ratio')
        plt.xlabel('Date (KST)')
        plt.xticks(rotation=45)
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        plt.savefig(f'{self.prefix}_oi_spike_detector.png', dpi=160, bbox_inches='tight')
        plt.close()
        
        print(f"   • {self.prefix}_oi_spike_detector.png  →  {status} ({latest_change:+.4f}) @ {latest_time_str}")
        print(f"     Thresholds (±95th percentile): ±{self.large_oi_threshold:.4f}")

    def run(self):
        self._basic_stats()
        self._large_oi_vs_price_scatter()
        self._fourteen_day_dual_chart()
        self._oi_spike_detector_chart()
        print(f"\n✅ {self.base}-{self.quote} OI Analysis complete! Charts saved:")
        print(f"   • {self.prefix}_large_oi_vs_price.png")
        print(f"   • {self.prefix}_oi_14d_standalone.png   ← stacked (Price top • OI bottom)")
        print(f"   • {self.prefix}_oi_spike_detector.png   ← TODAY always highlighted with exact time!")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        base, quote = "btc", "eth"
        print("No arguments → defaulting to BTC/ETH")
    elif len(sys.argv) == 3:
        base, quote = sys.argv[1].lower(), sys.argv[2].lower()
    else:
        print("Usage: python analyze_oi_standalone.py [SYMBOL1 SYMBOL2]")
        print("Example: python analyze_oi_standalone.py cake btc")
        sys.exit(1)
    
    analyzer = PairOIAnalyzerStandalone(base=base, quote=quote)
    analyzer.run()
