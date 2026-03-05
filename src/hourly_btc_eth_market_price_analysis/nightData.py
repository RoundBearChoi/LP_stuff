import pandas as pd
import os

class NightDataProcessor:
    """
    Loads btc_eth_prices_kst_10am_10pm_2years.csv and creates nightly paired rows
    • 10pm (current day) → 10am (next day)
    • Ratio_Difference     = End_ratio (10am next) - Start_ratio (10pm)
    • Ratio_Relative_Change = (End_ratio - Start_ratio) / Start_ratio   ← decimal form (NOT %)
    
    ROBUST MODE: auto-skips any incomplete night pair
    """

    def __init__(self, input_file='btc_eth_prices_kst_10am_10pm_2years.csv'):
        self.input_file = input_file
        self.output_file = 'btc_eth_night_paired.csv'

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

    def create_nightly_pairs(self):
        df = self.load_data()
        night_rows = []
        skipped = 0

        # Get all unique dates in order
        dates = sorted(df['Date'].unique())
        
        for i in range(len(dates) - 1):
            date_current = dates[i]
            date_next = dates[i + 1]
            
            group_current = df[df['Date'] == date_current].sort_values('KST_Datetime').reset_index(drop=True)
            group_next = df[df['Date'] == date_next].sort_values('KST_Datetime').reset_index(drop=True)
            
            if len(group_current) < 2 or len(group_next) < 1:
                print(f"⚠️  Skipping night {date_current}→{date_next} (incomplete data)")
                skipped += 1
                continue

            pm = group_current.iloc[1]      # 10pm of current day (iloc[1] = second record)
            am_next = group_next.iloc[0]    # 10am of next day (iloc[0] = first record)

            if pd.isna(pm['BTC_Price']) or pd.isna(pm['ETH_Price']) or \
               pd.isna(am_next['BTC_Price']) or pd.isna(am_next['ETH_Price']):
                print(f"⚠️  Skipping night {date_current}→{date_next} (missing prices)")
                skipped += 1
                continue

            start_ratio = pm['BTC_ETH_Ratio']
            end_ratio = am_next['BTC_ETH_Ratio']

            ratio_diff = end_ratio - start_ratio
            ratio_rel_change = (end_ratio - start_ratio) / start_ratio if start_ratio != 0 else 0.0

            row = [
                pm['KST_Datetime'].strftime('%Y-%m-%d %H:%M KST'), pm['Time_of_Day'], pm['BTC_Price'], pm['ETH_Price'], round(start_ratio, 10),
                am_next['KST_Datetime'].strftime('%Y-%m-%d %H:%M KST'), am_next['Time_of_Day'], am_next['BTC_Price'], am_next['ETH_Price'], round(end_ratio, 10),
                ratio_diff, ratio_rel_change
            ]
            night_rows.append(row)

        columns = ['KST_Datetime','Time_of_Day','BTC_Price','ETH_Price','BTC_ETH_Ratio',
                   'KST_Datetime','Time_of_Day','BTC_Price','ETH_Price','BTC_ETH_Ratio',
                   'Ratio_Difference','Ratio_Relative_Change']

        result_df = pd.DataFrame(night_rows, columns=columns)
        result_df.to_csv(self.output_file, index=False, float_format='%.16f')

        print(f"\n🎉 Success! Created {len(result_df):,} nightly rows.")
        print(f"   Skipped {skipped} incomplete night(s)")
        print(f"💾 Saved to → {self.output_file}")

        print("\nPreview of LAST valid row:")
        print(result_df.tail(1)[['Ratio_Difference', 'Ratio_Relative_Change']].to_string(index=False))

        return result_df


if __name__ == "__main__":
    processor = NightDataProcessor()
    processor.create_nightly_pairs()
