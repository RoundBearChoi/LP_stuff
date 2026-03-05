import pandas as pd
import os

class DayDataProcessor:
    """
    Loads btc_eth_prices_kst_10am_10pm_2years.csv and creates daily paired rows
    • Ratio_Difference     = PM_ratio - AM_ratio
    • Ratio_Relative_Change = (PM_ratio - AM_ratio) / AM_ratio   ← decimal form (NOT %)
    
    ROBUST MODE: auto-skips any day with missing prices
    """

    def __init__(self, input_file='btc_eth_prices_kst_10am_10pm_2years.csv'):
        self.input_file = input_file
        self.output_file = 'btc_eth_day_paired.csv'

    def load_data(self):
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"❌ Input file '{self.input_file}' not found!")

        df = pd.read_csv(self.input_file)
        print(f"✅ Loaded {len(df):,} records from {self.input_file}")

        df['KST_Datetime'] = pd.to_datetime(
            df['KST_Datetime'].str.replace(' KST', '', regex=False),
            format='%Y-%m-%d %H:%M'
        )
        df['Date'] = df['KST_Datetime'].dt.date
        df['BTC_Price'] = pd.to_numeric(df['BTC_Price'], errors='coerce')
        df['ETH_Price'] = pd.to_numeric(df['ETH_Price'], errors='coerce')
        df['BTC_ETH_Ratio'] = df['BTC_Price'] / df['ETH_Price']

        return df.sort_values('KST_Datetime').reset_index(drop=True)

    def create_daily_pairs(self):
        df = self.load_data()
        daily_rows = []
        skipped = 0

        for date, group in df.groupby('Date'):
            group = group.sort_values('KST_Datetime').reset_index(drop=True)
            if len(group) < 2:
                print(f"⚠️  Skipping {date} (only {len(group)} record(s))")
                skipped += 1
                continue

            am = group.iloc[0]
            pm = group.iloc[1]

            if pd.isna(am['BTC_Price']) or pd.isna(am['ETH_Price']) or \
               pd.isna(pm['BTC_Price']) or pd.isna(pm['ETH_Price']):
                print(f"⚠️  Skipping {date} (missing prices)")
                skipped += 1
                continue

            am_ratio = am['BTC_ETH_Ratio']
            pm_ratio = pm['BTC_ETH_Ratio']

            ratio_diff = pm_ratio - am_ratio
            ratio_rel_change = (pm_ratio - am_ratio) / am_ratio if am_ratio != 0 else 0.0

            row = [
                am['KST_Datetime'].strftime('%Y-%m-%d %H:%M KST'), am['Time_of_Day'], am['BTC_Price'], am['ETH_Price'], round(am_ratio, 10),
                pm['KST_Datetime'].strftime('%Y-%m-%d %H:%M KST'), pm['Time_of_Day'], pm['BTC_Price'], pm['ETH_Price'], round(pm_ratio, 10),
                ratio_diff, ratio_rel_change
            ]
            daily_rows.append(row)

        columns = ['KST_Datetime','Time_of_Day','BTC_Price','ETH_Price','BTC_ETH_Ratio',
                   'KST_Datetime','Time_of_Day','BTC_Price','ETH_Price','BTC_ETH_Ratio',
                   'Ratio_Difference','Ratio_Relative_Change']

        result_df = pd.DataFrame(daily_rows, columns=columns)
        result_df.to_csv(self.output_file, index=False, float_format='%.16f')

        print(f"\n🎉 Success! Created {len(result_df):,} daily rows.")
        print(f"   Skipped {skipped} incomplete day(s)")
        print(f"💾 Saved to → {self.output_file}")

        print("\nPreview of LAST valid row:")
        print(result_df.tail(1)[['Ratio_Difference', 'Ratio_Relative_Change']].to_string(index=False))

        return result_df


if __name__ == "__main__":
    processor = DayDataProcessor()
    processor.create_daily_pairs()
