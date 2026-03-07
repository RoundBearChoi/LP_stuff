import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import timedelta
import warnings
import sys
from pathlib import Path

warnings.filterwarnings('ignore')

sns.set_style("darkgrid")
plt.rcParams['figure.figsize'] = (22, 15)
plt.rcParams['font.size'] = 13


class AerodromeVolatilityAnalyzer:
    """Analyzer for ANY Aerodrome Slipstream pool volatility patterns (15-minute candles).
    Fully dynamic — works with any base/quote pair from the fetcher."""

    def __init__(self, base_symbol: str = "weth", quote_symbol: str = "cbbtc"):
        # ====================== CONFIG (now dynamic) ======================
        self.base = base_symbol.lower()
        self.quote = quote_symbol.lower()
        self.pair_name = f"{self.base.upper()}-{self.quote.upper()}"
        self.pair_slug = f"{self.base}_{self.quote}"

        self.CSV_FILE = f"aerodrome_{self.pair_slug}_15min_recent.csv"

        # Will be populated during run()
        self.df = None
        self.grouped = None
        self.bucket_stats = None
        self.bucket_order = None
        self.hourly_trend = None
        self.stats_hourly = None
        self.final_df = None

        print(f"🔍 Analyzing pool: {self.pair_name}")
        print(f"📂 Looking for: {self.CSV_FILE}\n")

    def run(self):
        """Main execution — produces CSV + TXT recommendations + dashboard + report."""
        self._load_data()
        self._analyze_3h_buckets()
        self._analyze_rolling_3h()
        self._generate_hourly_recommendations()
        self._generate_dashboard()
        self._write_report()
        print("\n🎉 ALL DONE! CSV + TXT recommendations + dashboard + report generated 🔥")

    def _load_data(self):
        csv_path = Path(self.CSV_FILE)
        if not csv_path.exists():
            print(f"❌ CSV not found: {self.CSV_FILE}")
            print("   Make sure you ran the fetcher first with the same pair.")
            sys.exit(1)

        self.df = pd.read_csv(self.CSV_FILE)
        self.df['datetime_utc'] = pd.to_datetime(self.df['datetime'])
        self.df['datetime_kst'] = self.df['datetime_utc'] + timedelta(hours=9)
        self.df = self.df.set_index('datetime_kst').sort_index()

        print(f"✅ Loaded {len(self.df):,} candles | {self.df.index[0].date()} → {self.df.index[-1].date()} KST")

    def _analyze_3h_buckets(self):
        self.df['date'] = self.df.index.date
        self.df['hour_kst'] = self.df.index.hour
        self.df['bucket_start'] = (self.df['hour_kst'] // 3) * 3

        self.grouped = self.df.groupby(['date', 'bucket_start']).agg({
            'high_usd': 'max', 'low_usd': 'min'
        }).reset_index()
        self.grouped['range_pct'] = (self.grouped['high_usd'] - self.grouped['low_usd']) / self.grouped['low_usd'] * 100
        self.grouped['time_bucket'] = self.grouped['bucket_start'].apply(lambda x: f'{x:02d}-{(x+3):02d}')

        self.bucket_order = [f'{i:02d}-{(i+3):02d}' for i in range(0, 24, 3)]
        self.bucket_stats = self.grouped.groupby('time_bucket')['range_pct'].agg([
            'count', 'median', ('p75', lambda x: x.quantile(0.75)), ('p90', lambda x: x.quantile(0.90))
        ]).round(3).reindex(self.bucket_order).reset_index()

    def _analyze_rolling_3h(self):
        window = 12
        self.df['rolling_high'] = self.df['high_usd'].rolling(window=window, min_periods=8).max()
        self.df['rolling_low'] = self.df['low_usd'].rolling(window=window, min_periods=8).min()
        self.df['rolling_range_pct'] = (self.df['rolling_high'] - self.df['rolling_low']) / self.df['rolling_low'] * 100

        self.hourly_trend = self.df.groupby('hour_kst')['rolling_range_pct'].agg(
            median='median', p75=lambda x: x.quantile(0.75), p90=lambda x: x.quantile(0.90)
        ).reindex(range(24))

    def _generate_hourly_recommendations(self):
        print("\n📊 Generating hourly recommendations...")

        self.df['hour_start'] = self.df.index.floor('h')
        hourly = self.df.groupby(['date', 'hour_start']).agg({
            'high_usd': 'max', 'low_usd': 'min'
        }).reset_index()
        hourly['range_pct'] = (hourly['high_usd'] - hourly['low_usd']) / hourly['low_usd'] * 100
        hourly['hour_kst'] = hourly['hour_start'].dt.hour

        self.stats_hourly = hourly.groupby('hour_kst')['range_pct'].agg([
            ('Samples', 'count'),
            ('Median', 'median'),
            ('P75', lambda x: x.quantile(0.75)),
            ('P90', lambda x: x.quantile(0.90))
        ]).round(3).reindex(range(24)).reset_index()

        self.stats_hourly['Bucket'] = self.stats_hourly['hour_kst'].apply(
            lambda x: f"{x:02d}:00 – {(x+1):02d}:00" if x < 23 else "23:00 – 00:00"
        )

        self.stats_hourly['Balanced']   = (self.stats_hourly['Median'] * 1.60).round(1)
        self.stats_hourly['Safe']       = (self.stats_hourly['Median'] * 1.80).round(1)
        self.stats_hourly['Aggressive'] = (self.stats_hourly['Median'] * 1.30).round(1)

        overall_median = hourly['range_pct'].median().round(3)
        overall_p75    = hourly['range_pct'].quantile(0.75).round(3)
        overall_p90    = hourly['range_pct'].quantile(0.90).round(3)

        overall_row = pd.DataFrame([{
            'Bucket':     'Overall Full 24h',
            'Median':     overall_median,
            'P75':        overall_p75,
            'P90':        overall_p90,
            'Balanced':   (overall_median * 1.60).round(1),
            'Safe':       (overall_median * 1.80).round(1),
            'Aggressive': (overall_median * 1.30).round(1),
            'Samples':    len(hourly)
        }])

        self.final_df = pd.concat([
            overall_row,
            self.stats_hourly[['Bucket', 'Median', 'P75', 'P90', 'Balanced', 'Safe', 'Aggressive', 'Samples']]
        ], ignore_index=True)

        cols_order = ['Bucket', 'Median', 'P75', 'P90', 'Balanced', 'Safe', 'Aggressive', 'Samples']
        self.final_df = self.final_df[cols_order]

        # Dynamic output names
        csv_out = f"{self.pair_slug}_hourly_recommendations.csv"
        txt_out = f"{self.pair_slug}_hourly_recommendations.txt"

        self.final_df.to_csv(csv_out, index=False)
        print(f"✅ CSV saved → {csv_out}")

        # Nicely formatted TXT
        with open(txt_out, 'w', encoding='utf-8') as f:
            f.write(f"{self.pair_name} Pool – Hourly Volatility Recommendations (KST)\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Data period:  {self.df.index.min().date()}  →  {self.df.index.max().date()}\n")
            f.write(f"Total hourly samples: {len(hourly):,}\n\n")

            header = f"{'Bucket':<18}  {'Median':>7}  {'P75':>6}  {'P90':>6}  " \
                     f"{'Balanced':>10}  {'Safe':>8}  {'Aggressive':>11}  {'Samples':>8}"
            f.write(header + "\n")
            f.write("-" * 80 + "\n")

            for _, row in self.final_df.iterrows():
                line = f"{row['Bucket']:<18}  " \
                       f"{row['Median']:7.3f}  " \
                       f"{row['P75']:6.3f}  " \
                       f"{row['P90']:6.3f}  " \
                       f"{row['Balanced']:10.1f}  " \
                       f"{row['Safe']:8.1f}  " \
                       f"{row['Aggressive']:11.1f}  " \
                       f"{int(row['Samples']):>8}"
                f.write(line + "\n")

            f.write("-" * 80 + "\n\n")
            f.write("Multiplier explanation:\n")
            f.write("• Balanced   = Median × 1.60\n")
            f.write("• Safe       = Median × 1.80\n")
            f.write("• Aggressive = Median × 1.30\n")

        print(f"📄 TXT report saved → {txt_out}")

        print("\nHourly recommendations preview:\n")
        print(self.final_df.to_string(index=False))

    def _generate_dashboard(self):
        print("\n🎨 Generating full dashboard PNG...")

        fig, axes = plt.subplots(2, 3, figsize=(22, 15))

        cutoff = self.df.index.max() - pd.Timedelta(days=90)
        recent_grouped = self.df[self.df.index >= cutoff].groupby(['date', 'bucket_start']).agg({
            'high_usd': 'max', 'low_usd': 'min'
        }).reset_index()
        recent_grouped['range_pct'] = (recent_grouped['high_usd'] - recent_grouped['low_usd']) / recent_grouped['low_usd'] * 100
        recent_grouped['time_bucket'] = recent_grouped['bucket_start'].apply(lambda x: f'{x:02d}-{(x+3):02d}')
        recent_stats = recent_grouped.groupby('time_bucket')['range_pct'].median().reindex(self.bucket_order)

        ax = axes[0, 0]
        x = np.arange(len(self.bucket_stats))
        ax.bar(x - 0.2, self.bucket_stats['median'], 0.2, label='Full History', color='#1f77b4')
        ax.bar(x, recent_stats, 0.2, label='Last 90d', color='#ff7f0e')
        ax.set_xticks(x)
        ax.set_xticklabels(self.bucket_order, rotation=45)
        ax.set_ylabel('% 3h Range')
        ax.set_title(f'3h Range by Time Bucket (KST) — {self.pair_name}')
        ax.legend()

        sns.boxplot(data=self.grouped, x='time_bucket', y='range_pct', ax=axes[0, 1], order=self.bucket_order, showfliers=False)
        axes[0, 1].set_xticklabels(axes[0, 1].get_xticklabels(), rotation=45)
        axes[0, 1].set_title('Full History Distribution')

        # Dynamic lines using your actual calculated values
        overall_balanced = self.final_df.iloc[0]['Balanced']
        overall_aggressive = self.final_df.iloc[0]['Aggressive']

        sns.histplot(self.grouped['range_pct'], bins=150, kde=True, ax=axes[0, 2], color='skyblue')
        axes[0, 2].axvline(overall_balanced, color='lime', ls='--', lw=2, label=f'Balanced ±{overall_balanced}%')
        axes[0, 2].axvline(overall_aggressive, color='purple', ls='--', lw=2, label=f'Aggressive ±{overall_aggressive}%')
        axes[0, 2].set_title(f'Overall 3h Range Distribution — {self.pair_name}')
        axes[0, 2].legend()

        ax = axes[1, 0]
        ax.plot(self.hourly_trend.index, self.hourly_trend['median'], 'o-', label='Median', color='#1f77b4', lw=3)
        ax.plot(self.hourly_trend.index, self.hourly_trend['p90'], '^-', label='90th', color='#d62728')
        ax.set_xticks(range(24))
        ax.set_xlabel('Hour (KST)')
        ax.set_title(f'Hourly 3h Range Trend (rolling) — {self.pair_name}')
        ax.legend()

        self.df['dow'] = self.df.index.dayofweek
        dow_hour = self.df.pivot_table(values='rolling_range_pct', index='dow', columns='hour_kst', aggfunc='median')
        sns.heatmap(dow_hour, cmap='YlOrRd', annot=True, fmt='.2f', ax=axes[1, 1])
        axes[1, 1].set_title(f'Median 3h Range by Day & Hour (KST)\n0=Mon … 6=Sun — {self.pair_name}')
        axes[1, 1].set_xlabel('Hour (KST)')
        axes[1, 1].set_ylabel('Day of Week')

        ax = fig.add_subplot(2, 3, 6, projection='polar')
        vals = self.hourly_trend['median'].values
        norm = plt.Normalize(vals.min(), vals.max())
        theta = np.linspace(0, 2 * np.pi, 24, endpoint=False)
        ax.bar(theta, vals, width=2 * np.pi / 24, color=plt.cm.RdYlGn_r(norm(vals)), alpha=0.9)
        ax.set_theta_zero_location('N')
        ax.set_theta_direction(-1)
        ax.set_xticks(theta)
        ax.set_xticklabels([f'{h:02d}' for h in range(24)])
        ax.set_title(f'24h Volatility Clock (KST) — {self.pair_name}')

        plt.tight_layout()

        png_out = f"{self.pair_slug}_3h_analysis_full.png"
        plt.savefig(png_out, dpi=180, bbox_inches='tight', pil_kwargs={'optimize': True, 'compress_level': 9})
        print(f"✅ Dashboard saved → {png_out}")

    def _write_report(self):
        report_out = f"{self.pair_slug}_volatility_report.txt"
        with open(report_out, 'w', encoding='utf-8') as f:
            f.write(f"{self.pair_name} Pool Volatility Report (KST)\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Period: {self.df.index[0].date()} → {self.df.index[-1].date()}\n\n")
            f.write(f"Most volatile 3h bucket: {self.bucket_stats.loc[self.bucket_stats['median'].idxmax(), 'time_bucket']} "
                    f"({self.bucket_stats['median'].max():.2f}%)\n")
            f.write(f"Calmest 3h bucket:   {self.bucket_stats.loc[self.bucket_stats['median'].idxmin(), 'time_bucket']} "
                    f"({self.bucket_stats['median'].min():.2f}%)\n\n")
            f.write(f"Hottest hour (1h):    {self.stats_hourly.loc[self.stats_hourly['Median'].idxmax(), 'Bucket']}\n")
            f.write(f"Calmest hour (1h):    {self.stats_hourly.loc[self.stats_hourly['Median'].idxmin(), 'Bucket']}\n\n")
            f.write(f"See {self.pair_slug}_hourly_recommendations.txt for detailed hourly ranges & suggested widths.\n")

        print(f"📋 Text report saved → {report_out}")


# ────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 2:
        base = sys.argv[1]
        quote = sys.argv[2]
        print(f"📥 Received command-line pair: {base.upper()}-{quote.upper()}")
    else:
        base = "weth"
        quote = "cbbtc"
        print("📥 Using default pair: WETH-cbBTC")

    analyzer = AerodromeVolatilityAnalyzer(base, quote)
    analyzer.run()
