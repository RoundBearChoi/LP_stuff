import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import timedelta
import warnings

warnings.filterwarnings('ignore')

sns.set_style("darkgrid")
plt.rcParams['figure.figsize'] = (22, 15)
plt.rcParams['font.size'] = 13


class WethCbBtcVolatilityAnalyzer:
    """Analyzer for WETH-cbBTC pool volatility patterns (15-minute candles)."""

    def __init__(self):
        # ====================== CONFIG ======================
        self.CSV_FILE = 'aerodrome_0x22aee3699b6a0fed71490c103bd4e5f3309891d5_15min_max2.0y.csv'
        self.ASSET = 'WETH-cbBTC Pool (USD)'

        # Will be populated during run()
        self.df = None
        self.grouped = None
        self.bucket_stats = None
        self.bucket_order = None
        self.hourly_trend = None
        self.stats_hourly = None
        self.final_df = None

    def run(self):
        """Main execution - produces the same outputs + new TXT hourly recommendations."""
        self._load_data()
        self._analyze_3h_buckets()
        self._analyze_rolling_3h()
        self._generate_hourly_recommendations()
        self._generate_dashboard()
        self._write_report()
        print("\n🎉 ALL DONE! CSV + TXT recommendations + dashboard + report generated 🔥")

    def _load_data(self):
        self.df = pd.read_csv(self.CSV_FILE)
        self.df['datetime_utc'] = pd.to_datetime(self.df['datetime'])
        self.df['datetime_kst'] = self.df['datetime_utc'] + timedelta(hours=9)
        self.df = self.df.set_index('datetime_kst').sort_index()

        print(f"✅ Loaded {len(self.df):,} candles | {self.df.index[0].date()} → {self.df.index[-1].date()} KST")

    def _analyze_3h_buckets(self):
        # ====================== 3H BUCKETS ======================
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
        # ====================== ROLLING 3H ======================
        window = 12  # 12 × 15min = 3 hours
        self.df['rolling_high'] = self.df['high_usd'].rolling(window=window, min_periods=8).max()
        self.df['rolling_low'] = self.df['low_usd'].rolling(window=window, min_periods=8).min()
        self.df['rolling_range_pct'] = (self.df['rolling_high'] - self.df['rolling_low']) / self.df['rolling_low'] * 100

        self.hourly_trend = self.df.groupby('hour_kst')['rolling_range_pct'].agg(
            median='median', p75=lambda x: x.quantile(0.75), p90=lambda x: x.quantile(0.90)
        ).reindex(range(24))

    def _generate_hourly_recommendations(self):
        # ====================== HOURLY RECOMMENDATIONS ======================
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

        # ────────────────────────────────────────────────
        # 1. Save as CSV
        self.final_df.to_csv('weth_cbbtc_hourly_recommendations.csv', index=False)
        print("✅ CSV saved → weth_cbbtc_hourly_recommendations.csv")

        # ────────────────────────────────────────────────
        # 2. Save as nicely formatted TXT
        with open('weth_cbbtc_hourly_recommendations.txt', 'w', encoding='utf-8') as f:
            f.write("WETH-cbBTC Pool – Hourly Volatility Recommendations (KST)\n")
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

        print("📄 TXT report saved → weth_cbbtc_hourly_recommendations.txt")

        # Optional: still show preview in console
        print("\nHourly recommendations preview:\n")
        print(self.final_df.to_string(index=False))

    def _generate_dashboard(self):
        # ====================== BIG DASHBOARD PNG ======================
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
        ax.set_title('3h Range by Time Bucket (KST)')
        ax.legend()

        sns.boxplot(data=self.grouped, x='time_bucket', y='range_pct', ax=axes[0, 1], order=self.bucket_order, showfliers=False)
        axes[0, 1].set_xticklabels(axes[0, 1].get_xticklabels(), rotation=45)
        axes[0, 1].set_title('Full History Distribution')

        sns.histplot(self.grouped['range_pct'], bins=150, kde=True, ax=axes[0, 2], color='skyblue')
        axes[0, 2].axvline(2.4, color='lime', ls='--', lw=2, label='Balanced ±2.4%')
        axes[0, 2].axvline(1.9, color='purple', ls='--', lw=2, label='Aggressive ±1.9%')
        axes[0, 2].set_title('Overall 3h Range Distribution')
        axes[0, 2].legend()

        ax = axes[1, 0]
        ax.plot(self.hourly_trend.index, self.hourly_trend['median'], 'o-', label='Median', color='#1f77b4', lw=3)
        ax.plot(self.hourly_trend.index, self.hourly_trend['p90'], '^-', label='90th', color='#d62728')
        ax.set_xticks(range(24))
        ax.set_xlabel('Hour (KST)')
        ax.set_title('Hourly 3h Range Trend (rolling)')
        ax.legend()

        self.df['dow'] = self.df.index.dayofweek
        dow_hour = self.df.pivot_table(values='rolling_range_pct', index='dow', columns='hour_kst', aggfunc='median')
        sns.heatmap(dow_hour, cmap='YlOrRd', annot=True, fmt='.2f', ax=axes[1, 1])
        axes[1, 1].set_title('Median 3h Range by Day & Hour (KST)\n0=Mon … 6=Sun')
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
        ax.set_title('24h Volatility Clock (KST)')

        plt.tight_layout()

        plt.savefig('weth_cbbtc_3h_analysis_full.png',
                    dpi=180,
                    bbox_inches='tight',
                    pil_kwargs={'optimize': True, 'compress_level': 9})

        print("✅ Dashboard saved → weth_cbbtc_3h_analysis_full.png")

    def _write_report(self):
        # ====================== SIMPLE TEXT REPORT ======================
        with open('weth_cbbtc_volatility_report.txt', 'w', encoding='utf-8') as f:
            f.write("WETH-cbBTC Pool Volatility Report (KST)\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Period: {self.df.index[0].date()} → {self.df.index[-1].date()}\n\n")
            f.write(f"Most volatile 3h bucket: {self.bucket_stats.loc[self.bucket_stats['median'].idxmax(), 'time_bucket']} "
                    f"({self.bucket_stats['median'].max():.2f}%)\n")
            f.write(f"Calmest 3h bucket:   {self.bucket_stats.loc[self.bucket_stats['median'].idxmin(), 'time_bucket']} "
                    f"({self.bucket_stats['median'].min():.2f}%)\n\n")
            f.write(f"Hottest hour (1h):    {self.stats_hourly.loc[self.stats_hourly['Median'].idxmax(), 'Bucket']}\n")
            f.write(f"Calmest hour (1h):    {self.stats_hourly.loc[self.stats_hourly['Median'].idxmin(), 'Bucket']}\n\n")
            f.write("See weth_cbbtc_hourly_recommendations.txt for detailed hourly ranges & suggested widths.\n")


if __name__ == "__main__":
    analyzer = WethCbBtcVolatilityAnalyzer()
    analyzer.run()
