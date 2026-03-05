import pandas as pd
import sys

class RatioQuickLook:
    """
    Quick-look analyzer for BTC/ETH ratio changes
    Works for BOTH day (10am→10pm) and night (10pm→10am next day)
    Just pass mode='day' or mode='night' (or use command line)
    """

    def __init__(self, mode='day', csv_file=None):
        self.mode = mode.lower().strip()
        if self.mode not in ['day', 'night']:
            raise ValueError("❌ mode must be 'day' or 'night'")

        self.df = None

        if csv_file is None:
            if self.mode == 'night':
                self.csv_file = 'btc_eth_night_paired.csv'
                self.output_sorted = 'btc_eth_night_ratio_sorted_by_change.csv'
                self.title = "BTC/ETH NIGHTLY RATIO CHANGE QUICK LOOK (22:00 → 10:00 KST next day)"
                self.unit_plural = "nights"
            else:  # day
                self.csv_file = 'btc_eth_day_paired.csv'
                self.output_sorted = 'btc_eth_ratio_sorted_by_change.csv'   # matches your original file name
                self.title = "BTC/ETH DAILY RATIO CHANGE QUICK LOOK (10:00 → 22:00 KST)"
                self.unit_plural = "days"
        else:
            # custom file provided
            self.csv_file = csv_file
            self.output_sorted = csv_file.replace('.csv', '_sorted_by_change.csv')
            self.title = "BTC/ETH RATIO CHANGE QUICK LOOK"
            self.unit_plural = "periods"

    def load_data(self):
        if not pd.io.common.file_exists(self.csv_file):
            raise FileNotFoundError(f"❌ File '{self.csv_file}' not found!")

        self.df = pd.read_csv(self.csv_file)

        change_col = 'Ratio_Relative_Change'
        if change_col not in self.df.columns:
            change_col = self.df.columns[-1]

        self.df['Change_%'] = self.df[change_col] * 100

        # FIXED: No more warnings
        self.df['Date'] = self.df.iloc[:, 0].str[:10]

        print(f"\n✅ Loaded {len(self.df):,} {self.unit_plural} from {self.csv_file}")
        print(f"   Period : {self.df.iloc[0]['Date']} → {self.df.iloc[-1]['Date']}")
        return self.df

    def analyze(self):
        if self.df is None:
            self.load_data()

        changes_pct = self.df['Change_%']

        print("\n" + "=" * 85)
        print(f"   {self.title}")
        print("=" * 85)

        print("\n📊 SUMMARY STATISTICS (% change)")
        print(f"   Mean           : {changes_pct.mean():+8.3f}%")
        print(f"   Median         : {changes_pct.median():+8.3f}%")
        print(f"   Std Dev        : {changes_pct.std():8.3f}%")
        print(f"   Min            : {changes_pct.min():+8.3f}%")
        print(f"   Max            : {changes_pct.max():+8.3f}%")

        print("\n📈 KEY PERCENTILES (% change)")
        for p in [1, 5, 10, 25, 50, 75, 90, 95, 99]:
            val = changes_pct.quantile(p / 100)
            print(f"   {p:2d}th percentile : {val:+8.3f}%")

        positive = (changes_pct > 0).sum()
        total = len(self.df)
        print(f"\n📌 Positive {self.unit_plural} : {positive:,} ({positive / total * 100:5.1f}%)")
        print(f"   Negative {self.unit_plural} : {total - positive:,} ({(total - positive) / total * 100:5.1f}%)")

        print(f"\n🔥 EXTREME {self.unit_plural.upper()}")
        print(f"   > +3.0% : {(changes_pct > 3.0).sum():3d} {self.unit_plural}")
        print(f"   > +2.0% : {(changes_pct > 2.0).sum():3d} {self.unit_plural}")
        print(f"   < -2.0% : {(changes_pct < -2.0).sum():3d} {self.unit_plural}")
        print(f"   < -3.0% : {(changes_pct < -3.0).sum():3d} {self.unit_plural}")

        sorted_df = self.df.sort_values('Change_%').copy()

        print(f"\n📉 8 WORST {self.unit_plural.upper()} (biggest ratio drops)")
        print(sorted_df.head(8)[['Date', 'Change_%']].round(3).to_string(index=False))

        print(f"\n🏆 8 BEST {self.unit_plural.upper()} (biggest ratio gains)")
        print(sorted_df.tail(8)[['Date', 'Change_%']].round(3).to_string(index=False))

        sorted_df.to_csv(self.output_sorted, index=False, float_format='%.6f')
        print(f"\n💾 Saved fully sorted file → {self.output_sorted}")

        return self.df


if __name__ == "__main__":
    # ==============================================
    # You can choose here OR use command line!
    # ==============================================
    mode = 'day'                     # ← change to 'night' if you want

    # Command-line override (recommended)
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower().strip()

    print(f"🚀 BTC/ETH Ratio Quick Look - {mode.upper()} mode\n")

    analyzer = RatioQuickLook(mode=mode)
    analyzer.analyze()
