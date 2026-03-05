import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
import sys


class RatioAnalyzer:
    """Unified BTC/ETH ratio analyzer for BOTH day (10am→10pm) and night (10pm→10am next day).
    Run with:  python statsLook.py          # day mode (default)
               python statsLook.py night    # night mode
               python statsLook.py day      # explicit day"""

    def __init__(self, mode: str = 'day'):
        self.mode = mode.lower().strip()
        if self.mode not in ['day', 'night']:
            raise ValueError("❌ mode must be 'day' or 'night'")

        if self.mode == 'night':
            self.csv_path = 'btc_eth_night_paired.csv'
            self.title_prefix = "NIGHTLY"
            self.period_desc = "(22:00 → 10:00 KST next day)"
            self.reference_time = "22:00"
            self.unit = "night"
            self.unit_plural = "nights"
        else:  # day
            self.csv_path = 'btc_eth_day_paired.csv'
            self.title_prefix = "DAILY"
            self.period_desc = "(10:00 → 22:00 KST)"
            self.reference_time = "10:00"
            self.unit = "day"
            self.unit_plural = "days"

        self._load_and_clean_data()

    def _load_and_clean_data(self):
        df = pd.read_csv(self.csv_path)
        # Keep only timestamp and the relative change (last column)
        df = df.iloc[:, [0, -1]].copy()
        df.columns = ['KST_Datetime', 'Ratio_Relative_Change']

        df['Date'] = pd.to_datetime(
            df['KST_Datetime'].str.replace(' KST', ''),
            errors='coerce'
        )
        df['Ratio_Relative_Change'] = pd.to_numeric(
            df['Ratio_Relative_Change'],
            errors='coerce'
        )

        df = df.dropna().set_index('Date')
        self.df = df
        self.changes = df['Ratio_Relative_Change']
        self.changes_np = self.changes.values
        self.abs_np = np.abs(self.changes_np)

        print(f"✅ Loaded {len(self.df):,} {self.unit_plural} from {self.csv_path}")
        print(f"Period     : {self.df.index.min().date()} → {self.df.index.max().date()}\n")

    # ====================== 2. OVERALL STATISTICS ======================
    def overall_statistics(self):
        print(f"=== OVERALL STATISTICS ({self.title_prefix}) ===")
        print("-" * 60)
        print(f"Mean               : {self.changes.mean():.6f}  ({self.changes.mean()*100:6.3f}%)")
        print(f"Median             : {self.changes.median():.6f}")
        print(f"Std Dev            : {self.changes.std():.6f}  (~{self.changes.std()*100:.2f}%)")
        print(f"Positive {self.unit_plural}   : {(self.changes > 0).mean()*100:.2f}%  ({(self.changes > 0).sum()}/{len(self.changes)})")

        t_stat, p_value = stats.ttest_1samp(self.changes, 0)
        print(f"\nT-test p-value (mean == 0) : {p_value:.4f} → {'Not significant' if p_value > 0.05 else 'Significant'}")

    # ====================== 3. MONTHLY BLOCK ANALYSIS ======================
    def monthly_block_analysis(self):
        print(f"\n=== MONTHLY BLOCK ANALYSIS ({self.title_prefix}) ===")
        print("-" * 60)

        monthly = self.df['Ratio_Relative_Change'].resample('ME').agg({
            'count': 'count',
            'mean': 'mean',
            'std': 'std',
            'positive_pct': lambda x: (x > 0).mean() * 100
        })

        monthly_display = monthly[['mean', 'positive_pct', 'count']].copy()
        monthly_display['mean'] = monthly_display['mean'] * 100

        print(monthly_display.round(4))
        monthly_display.to_csv(f'ratio_monthly_blocks_{self.mode}.csv')
        print(f"\n📁 Monthly blocks saved → ratio_monthly_blocks_{self.mode}.csv")

    # ====================== 4. ROLLING 30-DAY BLOCKS ======================
    def rolling_30day_blocks(self):
        print(f"\n=== ROLLING 30-{self.unit.capitalize()} BLOCKS (last 10 shown) ===")
        rolling = self.df['Ratio_Relative_Change'].rolling(window=30, min_periods=15).agg({
            'mean': 'mean',
            'positive_pct': lambda x: (x > 0).mean() * 100
        })
        print(rolling.tail(10).round(4))

    # ====================== 5. BLOCK BOOTSTRAP - OVERALL MEAN ======================
    def block_bootstrap_overall_mean(self):
        print("\n" + "="*70)
        print(f"=== BLOCK BOOTSTRAP ANALYSIS ({self.title_prefix}) ===")
        print("="*70)

        print(f"Using {len(self.changes_np):,} {self.unit_plural} | Block size = 21 {self.unit}s")

        np.random.seed(42)
        boot_means = self._moving_block_bootstrap(self.changes_np, block_size=21, n_boot=5000)

        mean_boot = boot_means.mean()
        ci95_mean = np.percentile(boot_means, [2.5, 97.5])
        p_boot = np.mean(np.abs(boot_means) >= np.abs(self.changes_np.mean())) * 2

        print(f"\nOverall mean relative change")
        print(f"   Original : {self.changes_np.mean():+.6f} ({self.changes_np.mean()*100:+.3f}%)")
        print(f"   Bootstrap mean : {mean_boot:+.6f}")
        print(f"   95% CI         : [{ci95_mean[0]:+.6f}, {ci95_mean[1]:+.6f}]")
        print(f"   Bootstrapped p-value (mean=0) : {p_boot:.4f} → {'Significant' if p_boot <= 0.05 else 'Not significant'}")

    @staticmethod
    def _moving_block_bootstrap(series, block_size=21, n_boot=5000):
        n = len(series)
        boot_means = np.empty(n_boot)
        n_blocks = int(np.ceil(n / block_size))
        for i in range(n_boot):
            starts = np.random.randint(0, n - block_size + 1, size=n_blocks)
            sample = np.concatenate([series[s:s+block_size] for s in starts])[:n]
            boot_means[i] = sample.mean()
        return boot_means

    # ====================== 6. DYNAMIC BALANCED RANGE ======================
    def setup_dynamic_balanced_range(self):
        print("\n" + "="*70)
        print("💡 DYNAMIC BALANCED RANGE SETUP")
        print("="*70)
        print("Choose how wide you want the range:")
        print("1) 95th percentile  → Wider / safer     (~±2.9%)")
        print("2) 90th percentile  → Recommended balance (~±2.2%)")
        print("3) 85th percentile  → Tighter           (~±1.8%)")
        print("4) Custom percentile")

        while True:
            choice = input("\nEnter 1-4 (or press Enter for default 90th): ").strip()
            if choice == "" or choice == "2":
                self.PERCENTILE = 90
                break
            elif choice == "1":
                self.PERCENTILE = 95
                break
            elif choice == "3":
                self.PERCENTILE = 85
                break
            elif choice == "4":
                try:
                    custom = float(input("Enter custom percentile (e.g. 92 or 88): "))
                    if 50 < custom < 100:
                        self.PERCENTILE = custom
                        break
                    else:
                        print("Please enter a number between 50 and 100.")
                except:
                    print("Invalid → using default 90")
                    self.PERCENTILE = 90
                    break
            else:
                print("Please enter 1, 2, 3 or 4.")

        print(f"✅ Using {self.PERCENTILE}th percentile")

        p = np.percentile(self.abs_np, self.PERCENTILE)
        balanced_range_pct = round(p * 100, 1)
        coverage_pct = (self.abs_np <= p).mean() * 100

        self.p = p
        self.balanced_range_pct = balanced_range_pct
        self.coverage_pct = coverage_pct

        print(f"\n💡 DYNAMIC BALANCED RANGE RECOMMENDATION ({self.PERCENTILE}th percentile)")
        print(f"   ±{balanced_range_pct}% around the {self.reference_time} KST ratio")
        print(f"   Covers {coverage_pct:.1f}% of all {len(self.changes)} historical {self.unit_plural}")

    # ====================== 7. BLOCK BOOTSTRAP FOR CHOSEN PERCENTILE ======================
    def block_bootstrap_percentile(self):
        print(f"\n🔬 Block-bootstrap 95% CI for your chosen {self.PERCENTILE}th percentile...")

        boot_p = self._bootstrap_percentile(self.abs_np, percentile=self.PERCENTILE, n_boot=3000)
        ci95_p = np.percentile(boot_p, [2.5, 97.5])

        self.boot_percentiles = boot_p
        self.ci95_p = ci95_p

        print(f"   Original {self.PERCENTILE}th percentile : ±{self.p*100:.1f}%")
        print(f"   Block-bootstrap 95% CI : ±[{ci95_p[0]*100:.1f}%, {ci95_p[1]*100:.1f}%]")

    @staticmethod
    def _bootstrap_percentile(data, percentile, block_size=21, n_boot=3000):
        n = len(data)
        n_blocks = int(np.ceil(n / block_size))
        boot_pcts = np.empty(n_boot)
        for i in range(n_boot):
            starts = np.random.randint(0, n - block_size + 1, size=n_blocks)
            sample = np.concatenate([data[s:s+block_size] for s in starts])[:n]
            boot_pcts[i] = np.percentile(np.abs(sample), percentile)
        return boot_pcts

    # ====================== 8. VISUALS + SAVE PNG ======================
    def generate_and_save_visuals(self):
        print("\n🎨 Saving final chart...")

        plt.figure(figsize=(14, 14), dpi=120)

        plt.subplot(3, 2, 1)
        sns.histplot(self.changes*100, bins=80, kde=True, color='skyblue')
        plt.axvline(0, color='red', linestyle='--')
        plt.xlabel('Change (%)')
        plt.title(f'Distribution of {self.title_prefix} Ratio Relative Change')

        plt.subplot(3, 2, 2)
        (self.changes*100).plot(alpha=0.7, color='steelblue')
        plt.axhline(0, color='red', linestyle='--', alpha=0.6)
        plt.ylabel('Change (%)')
        plt.title(f'{self.title_prefix} Ratio_Relative_Change {self.period_desc}')

        plt.subplot(3, 2, 3)
        monthly = self.df['Ratio_Relative_Change'].resample('ME').mean()
        monthly.plot(kind='bar', color='lightcoral')
        plt.axhline(0, color='black', linestyle='--')
        plt.title('Monthly Mean Relative Change')
        plt.xticks(rotation=45)

        plt.subplot(3, 2, 4)
        rolling = self.df['Ratio_Relative_Change'].rolling(window=30, min_periods=15).mean()
        rolling.plot(color='darkorange')
        plt.axhline(0, color='red', linestyle='--')
        plt.title(f'30-{self.unit.capitalize()}-Rolling Mean (regime detector)')

        # Bootstrap histogram
        plt.subplot(3, 2, 5)
        sns.histplot(self.boot_percentiles * 100, bins=60, kde=True, color='mediumpurple')
        plt.axvline(self.p*100, color='red', linestyle='--', linewidth=2.5, label=f'Original ({self.p*100:.1f}%)')
        plt.axvline(self.ci95_p[0]*100, color='black', linestyle='--', linewidth=1.5, label='95% CI lower')
        plt.axvline(self.ci95_p[1]*100, color='black', linestyle='--', linewidth=1.5, label='95% CI upper')
        plt.xlabel(f'Bootstrapped {self.PERCENTILE}th Percentile of |Change| (%)')
        plt.title('Block-Bootstrap Distribution of Chosen Percentile')
        plt.legend(fontsize=9, loc='upper right')

        plt.tight_layout(rect=[0, 0.085, 1, 0.96])

        plt.figtext(0.5, 0.015,
                    f"DYNAMIC BALANCED RANGE for cbBTC-ETH pool {self.period_desc}\n"
                    f"±{self.balanced_range_pct}% around the {self.reference_time} KST ratio • "
                    f"Covers {self.coverage_pct:.1f}% of {len(self.changes)} historical {self.unit_plural}\n"
                    f"Block-bootstrap 95% CI for {self.PERCENTILE}th percentile: [{self.ci95_p[0]*100:.1f}%, {self.ci95_p[1]*100:.1f}%]",
                    ha='center', va='bottom', fontsize=11, fontweight='bold',
                    bbox=dict(boxstyle="round,pad=1.0", facecolor="#E6F3FF", edgecolor="#1E88E5", linewidth=2))

        png_filename = f"ratio_{self.mode}_analysis_{int(self.PERCENTILE)}.png"
        plt.savefig(png_filename,
                    dpi=120,
                    bbox_inches='tight',
                    pil_kwargs={'compression': 9, 'optimize': True})
        plt.close()

        print(f"\n📸 Chart saved → {png_filename}")

    # ====================== RUN EVERYTHING ======================
    def run(self):
        self.overall_statistics()
        self.monthly_block_analysis()
        self.rolling_30day_blocks()
        self.block_bootstrap_overall_mean()
        self.setup_dynamic_balanced_range()
        self.block_bootstrap_percentile()
        self.generate_and_save_visuals()


# ====================== ENTRY POINT ======================
if __name__ == "__main__":
    mode = 'day'
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower().strip()

    print(f"🚀 BTC/ETH Ratio Full Stats Analyzer - {mode.upper()} mode\n")

    analyzer = RatioAnalyzer(mode=mode)
    analyzer.run()
