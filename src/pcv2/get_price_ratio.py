import sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')                # Non-interactive (no window ever appears)
import matplotlib.pyplot as plt
from datetime import datetime


class PriceRatioChart:
    """Clean, reusable class to generate price ratio charts from your CSV."""

    CSV_FILE = 'top100_hourly_1year_combined.csv'   # Your exact file (same folder)

    def __init__(self):
        """Initialize with default settings."""
        pass

    def parse_arguments(self):
        """Parse command-line args or default to BTC/ETH."""
        if len(sys.argv) == 3:
            symbol1 = sys.argv[1].upper().strip()
            symbol2 = sys.argv[2].upper().strip()
            print(f"Generating ratio chart for {symbol1} / {symbol2}")
            return symbol1, symbol2
        else:
            print("No symbols provided → defaulting to BTC / ETH")
            return 'BTC', 'ETH'

    def run(self):
        """Main execution flow — identical behavior to previous version."""
        symbol1, symbol2 = self.parse_arguments()

        print(f"Loading {self.CSV_FILE}... (this may take a few seconds)")
        df = pd.read_csv(self.CSV_FILE)

        # Prepare data
        df['symbol'] = df['symbol'].astype(str).str.upper()
        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        df = df.dropna(subset=['datetime', 'close'])

        print(f"Total rows loaded: {len(df):,}")

        # Filter symbols
        df1 = df[df['symbol'] == symbol1].copy()
        df2 = df[df['symbol'] == symbol2].copy()

        if df1.empty:
            print(f"❌ Symbol '{symbol1}' not found in the CSV.")
            sys.exit(1)
        if df2.empty:
            print(f"❌ Symbol '{symbol2}' not found in the CSV.")
            sys.exit(1)

        print(f"Found data for {symbol1} and {symbol2}")

        # Merge on exact datetime
        merged = pd.merge(
            df1[['datetime', 'close']],
            df2[['datetime', 'close']],
            on='datetime',
            how='inner',
            suffixes=(f'_{symbol1}', f'_{symbol2}')
        )

        if len(merged) == 0:
            print("❌ No overlapping hourly data between the two assets.")
            sys.exit(1)

        print(f"Calculating ratio over {len(merged):,} common hours...")

        # Calculate ratio
        merged['ratio'] = merged[f'close_{symbol1}'] / merged[f'close_{symbol2}']

        # ====================== CREATE & SAVE CHART (SILENT) ======================
        plt.figure(figsize=(14, 7))

        plt.plot(merged['datetime'], merged['ratio'],
                 label=f'{symbol1} / {symbol2} Price Ratio',
                 color='#006400', linewidth=2.5)   # Dark professional green

        plt.title(f'Price Ratio: {symbol1} ÷ {symbol2}\n'
                  f'{merged["datetime"].min().strftime("%Y-%m-%d %H:%M")} → '
                  f'{merged["datetime"].max().strftime("%Y-%m-%d %H:%M")}',
                  fontsize=16, fontweight='bold')

        plt.xlabel('Date (Hourly)', fontsize=12)
        plt.ylabel(f'{symbol1} / {symbol2} Ratio', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend(fontsize=12)

        plt.xticks(rotation=45)
        plt.tight_layout()

        # Save (simple filename, no window)
        save_name = f"ratio_{symbol1}_{symbol2}.png"
        plt.savefig(save_name, dpi=300, bbox_inches='tight')
        plt.close()

        print("\n✅ SUCCESS! Chart saved silently.")
        print(f"   File: {save_name}")
        print(f"   Data points: {len(merged):,} hourly candles")
        print(f"   Time period: {merged['datetime'].min().strftime('%Y-%m-%d')} → {merged['datetime'].max().strftime('%Y-%m-%d')}")


# ====================== RUN THE CLASS ======================
if __name__ == "__main__":
    chart = PriceRatioChart()
    chart.run()
