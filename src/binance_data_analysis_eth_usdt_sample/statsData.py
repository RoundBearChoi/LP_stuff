import ccxt
import pandas as pd
import pytz
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.gridspec as gridspec
import numpy as np
from datetime import datetime, timedelta

class UniswapV3StatsAnalyzer:
    """
    Full 24h KST analysis in ONE clean dashboard.
    Volatility Clock with extra top breathing room + hour numbers snug to the circle.
    """

    def __init__(self, symbol: str = 'ETH/USDT', timeframe: str = '15m', days_back: int = 730, chart_dpi: int = 165):
        self.symbol = symbol
        self.timeframe = timeframe
        self.days_back = days_back
        self.chart_dpi = chart_dpi
        self.full_df = None
        self.df_24h = None
        self.exchange = None

    def fetch_data(self):
        print(f"Fetching {self.days_back} days of {self.timeframe} {self.symbol} data... (~20-40s)")

        self.exchange = ccxt.binance({'enableRateLimit': True})

        since = int((datetime.now(pytz.utc) - timedelta(days=self.days_back)).timestamp() * 1000)
        all_ohlcv = []

        while True:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=since, limit=1000)
            if not ohlcv:
                break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < 1000:
                break

        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('Asia/Seoul')
        df = df.set_index('timestamp').sort_index()

        self.full_df = df.copy()
        self.df_24h = df.copy()

        print(f"Loaded {len(self.df_24h):,} candles (Full 24h KST).")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.symbol.replace('/', '_')
        self.full_df.to_csv(f"{base}_{self.timeframe}_full_kst_{ts}.csv")
        self.df_24h.to_csv(f"{base}_{self.timeframe}_24h_kst_{ts}.csv")
        print(f"✅ Raw data saved to script folder\n")

    def compute_window_stats(self, sub_df: pd.DataFrame, label: str):
        print(f"=== {label} ===")
        for hours in [2, 3]:
            periods = int(hours * 60 / 15) if self.timeframe == '15m' else hours
            sub_df[f'{hours}h_return'] = sub_df['close'].pct_change(periods) * 100
            sub_df[f'{hours}h_range'] = (
                sub_df['high'].rolling(periods).max() -
                sub_df['low'].rolling(periods).min()
            ) / sub_df['close'].shift(periods) * 100

            print(f"\n{hours}h Rolling:")
            stats = sub_df[[f'{hours}h_return', f'{hours}h_range']].describe(
                percentiles=[0.5, 0.75, 0.9, 0.95]
            )
            print(stats.round(3))

            print("  Per-bucket median range:")
            for s, e in [('00:00','03:00'), ('03:00','06:00'), ('06:00','09:00'), ('09:00','12:00'),
                        ('12:00','15:00'), ('15:00','18:00'), ('18:00','21:00'), ('21:00','00:00')]:
                bucket = sub_df.between_time(s, e)
                print(f"    {s}-{e if e != '00:00' else '24:00'}: {bucket[f'{hours}h_range'].median():.3f}%")
        print("")

    def generate_charts(self):
        if self.df_24h is None or '3h_range' not in self.df_24h.columns:
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.symbol.replace('/', '_')
        sns.set_style("darkgrid")

        # Prepare data
        bucket_intervals = [
            ('00:00','03:00'), ('03:00','06:00'), ('06:00','09:00'), ('09:00','12:00'),
            ('12:00','15:00'), ('15:00','18:00'), ('18:00','21:00'), ('21:00','00:00')
        ]
        bucket_names = ['00-03', '03-06', '06-09', '09-12', '12-15', '15-18', '18-21', '21-24']

        buckets = [self.df_24h.between_time(s, e)['3h_range'].dropna() for s, e in bucket_intervals]
        bucket_df = pd.DataFrame(dict(zip(bucket_names, buckets)))

        # Hourly data
        hourly_medians = []
        hourly_p75 = []
        hourly_p90 = []
        colors = []
        hour_labels = [f"{h:02d}" for h in range(24)]

        for h in range(24):
            start = f"{h:02d}:00"
            end = f"{(h + 1) % 24:02d}:00"
            bucket = self.df_24h.between_time(start, end)['3h_range'].dropna()
            hourly_medians.append(bucket.median())
            hourly_p75.append(bucket.quantile(0.75))
            hourly_p90.append(bucket.quantile(0.90))

        med_series = pd.Series(hourly_medians)
        low_thresh = med_series.quantile(0.33)
        high_thresh = med_series.quantile(0.67)
        for m in hourly_medians:
            if m <= low_thresh:
                colors.append('#2ca02c')
            elif m >= high_thresh:
                colors.append('#d62728')
            else:
                colors.append('#ff7f0e')

        # === ONE CLEAN DASHBOARD ===
        fig = plt.figure(figsize=(22, 25.5))   # extra height for more top space
        gs = gridspec.GridSpec(3, 2, figure=fig, height_ratios=[2.5, 5.0, 6.5], hspace=0.38, wspace=0.28)

        # Top: VOLATILITY CLOCK
        clock_ax = fig.add_subplot(gs[0, :], projection='polar')
        theta = np.linspace(0, 2*np.pi, 24, endpoint=False)
        width = 2 * np.pi / 24
        clock_ax.bar(theta, 1.0, width=width, color=colors, edgecolor='white', linewidth=2.8)

        clock_ax.set_yticks([])
        clock_ax.set_xticks([])
        clock_ax.set_theta_zero_location('N')
        clock_ax.set_theta_direction(-1)
        clock_ax.set_title('24h Volatility Clock\n(Green = Lowest • Orange = Medium • Red = Highest)',
                           fontsize=15, pad=25, y=1.05)

        # Hour numbers CLOSER to the circle (1.26 instead of 1.42)
        for i in range(24):
            angle = i * (2 * np.pi / 24)
            clock_ax.text(angle, 1.26, hour_labels[i], ha='center', va='center',
                          rotation=(np.degrees(angle) - 90 if np.degrees(angle) < 180 else np.degrees(angle) + 90),
                          fontsize=10.5, fontweight='bold')

        # Row 2: Bar + Boxplot
        ax_bar = fig.add_subplot(gs[1, 0])
        medians = [b.median() for b in buckets]
        p75 = [b.quantile(0.75) for b in buckets]
        p90 = [b.quantile(0.90) for b in buckets]
        x = range(8)
        ax_bar.bar(x, medians, color='#1f77b4', alpha=0.8, label='Median 3h range')
        ax_bar.errorbar(x, medians, yerr=[[0]*8, [p75[i]-medians[i] for i in x]], fmt='none', ecolor='orange', capsize=6, label='75th')
        ax_bar.errorbar(x, medians, yerr=[[0]*8, [p90[i]-medians[i] for i in x]], fmt='none', ecolor='red', capsize=6, label='90th')
        ax_bar.set_xticks(x)
        ax_bar.set_xticklabels(bucket_names)
        ax_bar.set_ylabel('% Range')
        ax_bar.set_title('3h Range by Time Bucket')
        ax_bar.legend()

        ax_box = fig.add_subplot(gs[1, 1])
        sns.boxplot(data=bucket_df, palette="Blues", ax=ax_box)
        ax_box.set_ylabel('% 3h Range')
        ax_box.set_title('Distribution by Time of Day')
        ax_box.set_xlabel('Time Bucket (KST)')

        # Row 3: Histogram + Hourly Trend
        ax_hist = fig.add_subplot(gs[2, 0])
        sns.histplot(self.df_24h['3h_range'], bins=80, kde=True, color='#1f77b4', ax=ax_hist)
        balanced = round(self.df_24h['3h_range'].quantile(0.75) * 1.10, 1)
        safe = round(self.df_24h['3h_range'].quantile(0.90) * 0.82, 1)
        agg = round(self.df_24h['3h_range'].quantile(0.75) * 0.88, 1)
        ax_hist.axvline(balanced, color='green', linestyle='--', linewidth=2.5, label=f'Balanced ±{balanced}%')
        ax_hist.axvline(safe, color='red', linestyle='--', linewidth=2.5, label=f'Safe ±{safe}%')
        ax_hist.axvline(agg, color='purple', linestyle='--', linewidth=2.5, label=f'Aggressive ±{agg}%')
        ax_hist.set_xlabel('% 3h Range')
        ax_hist.set_title('Overall 3h Range Distribution (~2 Years)')
        ax_hist.legend()

        ax_trend = fig.add_subplot(gs[2, 1])
        x_trend = range(24)
        ax_trend.plot(x_trend, hourly_medians, marker='o', linewidth=3, color='#1f77b4', label='Median 3h range')
        ax_trend.plot(x_trend, hourly_p75, marker='s', linestyle='--', linewidth=2, color='orange', label='75th')
        ax_trend.plot(x_trend, hourly_p90, marker='^', linestyle='--', linewidth=2, color='red', label='90th')
        ax_trend.set_xticks(x_trend)
        ax_trend.set_xticklabels(hour_labels, rotation=45, ha='right')
        ax_trend.set_ylabel('% 3h Range')
        ax_trend.set_title('Hourly 3h Range Trend')
        ax_trend.grid(True, alpha=0.3)
        ax_trend.legend()

        # Main title with generous top space
        fig.suptitle(
            f'{self.symbol} Full 24h Uniswap V3 3h Range Analysis (KST)\n'
            f'~2 Years • {len(self.df_24h):,} candles',
            fontsize=18, y=0.97
        )
        fig.subplots_adjust(top=0.895, bottom=0.06, hspace=0.38)   # tuned for extra top breathing room

        plt.savefig(f"{base}_combined_24h_{ts}.png", dpi=self.chart_dpi, bbox_inches='tight')
        plt.close()

        print(f"✅ Dashboard with more top space + closer clock numbers saved → {base}_combined_24h_{ts}.png\n")

    def print_range_recommendations(self):
        print("\n" + "="*90)
        print("🚀 UNISWAP V3 LP RANGE RECOMMENDATIONS (3-hour horizon)")
        print("                      FULL 24 HOURS KST")
        print("="*90)

        def print_recs(label, range_series):
            series = range_series.dropna()
            if len(series) < 100:
                print(f"\n{label}: Not enough data")
                return
            p75 = series.quantile(0.75)
            p90 = series.quantile(0.90)
            balanced = round(p75 * 1.10, 1)
            safe     = round(p90 * 0.82, 1)
            agg      = round(p75 * 0.88, 1)
            print(f"\n{label}:")
            print(f"   Balanced     → ±{balanced}%")
            print(f"   Safe         → ±{safe}%")
            print(f"   Aggressive   → ±{agg}%")
            return balanced, safe, agg, round(series.median(), 3), round(p75, 3), round(p90, 3), len(series)

        recs_list = []
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = self.symbol.replace('/', '_')

        print("Overall (full 24h):")
        res = print_recs("Full 24h", self.df_24h['3h_range'])
        if res:
            balanced, safe, agg, med, p75v, p90v, samples = res
            recs_list.append(['Overall Full 24h', med, p75v, p90v, balanced, safe, agg, samples])

        print("\n" + "-"*80)
        print("🕒 HOURLY RECOMMENDATIONS")
        print("-"*80)
        for h in range(24):
            start = f"{h:02d}:00"
            end   = f"{(h + 1) % 24:02d}:00"
            name  = f"{start} – {end}"
            bucket = self.df_24h.between_time(start, end)
            res = print_recs(name, bucket['3h_range'])
            if res:
                balanced, safe, agg, med, p75v, p90v, samples = res
                recs_list.append([name, med, p75v, p90v, balanced, safe, agg, samples])

        df_recs = pd.DataFrame(recs_list, columns=[
            'Bucket', 'Median', 'P75', 'P90', 'Balanced', 'Safe', 'Aggressive', 'Samples'
        ])
        csv_path = f"{base}_hourly_recommendations_{ts}.csv"
        df_recs.to_csv(csv_path, index=False)
        print(f"\n✅ Hourly recommendations CSV saved → {csv_path}")

        print("\n✅ Done! Run weekly for fresh numbers & charts.")

    def run(self):
        self.fetch_data()
        if self.df_24h is None or len(self.df_24h) == 0:
            print("Error: No data.")
            return

        now = self.df_24h.index.max()
        self.compute_window_stats(self.df_24h, "FULL 2 YEARS")
        self.compute_window_stats(self.df_24h[self.df_24h.index > now - pd.Timedelta(days=365)], "LAST 1 YEAR")
        self.compute_window_stats(self.df_24h[self.df_24h.index > now - pd.Timedelta(days=180)], "LAST 6 MONTHS")

        self.generate_charts()
        self.print_range_recommendations()


# ====================== RUN ======================
if __name__ == "__main__":
    analyzer = UniswapV3StatsAnalyzer(
        symbol='ETH/USDT',   # ← change to 'BTC/USDT' anytime
        timeframe='15m',
        days_back=730,
        chart_dpi=165        # 145 = smaller, 180 = sharper
    )
    analyzer.run()
