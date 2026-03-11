import sys
import pandas as pd
import matplotlib.pyplot as plt   # ← Agg removed so chart shows + pauses


class PriceRatioChart:
    """Clean, reusable class to generate price ratio charts from your CSV."""

    CSV_FILE = 'top100_hourly_1year_combined.csv'   # Your exact file (same folder)

    # ==================== TUNABLE SETTINGS (change these only) ====================
    MA_PERIOD = 168                     # hours (168 = 7 days)
    RSI_PERIOD = 14
    RATIO_LINE_WIDTH = 1                # ← thinner raw ratio line
    MA_LINE_WIDTH = 2.4                 # ← thinner colored MA line
    # =============================================================================

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

    def calculate_rsi(self, series):
        """Simple RSI calculation on the ratio series."""
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def run(self):
        """Main execution flow — thinner lines + show + pause."""
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

        merged['ratio'] = merged[f'close_{symbol1}'] / merged[f'close_{symbol2}']

        # ====================== CALCULATE MA + RSI ======================
        print(f"Calculating {self.MA_PERIOD}-hour MA + RSI({self.RSI_PERIOD})...")
        merged['rsi'] = self.calculate_rsi(merged['ratio'])
        merged['ma'] = merged['ratio'].rolling(window=self.MA_PERIOD).mean()

        # Drop early NaNs from rolling calculations
        merged = merged.dropna(subset=['rsi', 'ma']).reset_index(drop=True)

        print(f"Plotting {len(merged):,} points with RSI coloring on the MA...")

        # ====================== CREATE CHART ======================
        fig, ax = plt.subplots(figsize=(14, 7))

        x = merged['datetime']
        y = merged['ratio']
        ma = merged['ma']
        rsi = merged['rsi']

        # 1. Thinner neutral raw ratio line (background)
        ax.plot(x, y,
                label=f'{symbol1} / {symbol2} Ratio',
                color='#0189FB', linewidth=self.RATIO_LINE_WIDTH, alpha=0.82)

        # 2. Thinner RSI-colored MA line (the star)
        for i in range(1, len(merged)):
            if rsi.iloc[i] > 70:
                color = '#e63939'      # deep red — heavily overbought
            elif rsi.iloc[i] > 60:
                color = '#f77f00'      # orange-red
            elif rsi.iloc[i] < 30:
                color = '#2a9d8e'      # strong teal-green — heavily oversold
            elif rsi.iloc[i] < 40:
                color = '#52b788'      # lighter green
            else:
                color = '#006400'      # neutral dark green

            ax.plot(x.iloc[i-1:i+1], ma.iloc[i-1:i+1], color=color, linewidth=self.MA_LINE_WIDTH)

        ax.set_title(f'Price Ratio: {symbol1} ÷ {symbol2}   |   {self.MA_PERIOD}-hour MA Colored by RSI({self.RSI_PERIOD})\n'
                     f'{merged["datetime"].min().strftime("%Y-%m-%d %H:%M")} → '
                     f'{merged["datetime"].max().strftime("%Y-%m-%d %H:%M")}',
                     fontsize=16, fontweight='bold')

        ax.set_xlabel('Date (Hourly)', fontsize=12)
        ax.set_ylabel(f'{symbol1} / {symbol2} Ratio', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=12)

        plt.xticks(rotation=45)
        plt.tight_layout()

        # ====================== SAVE + SHOW & PAUSE ======================
        save_name = f"ratio_{symbol1}_{symbol2}.png"
        plt.savefig(save_name, dpi=200, bbox_inches='tight')
        
        print("\n✅ SUCCESS! Chart saved AND displayed.")
        print(f"   File: {save_name}")
        print(f"   Data points: {len(merged):,} hourly candles")
        print(f"   MA period: {self.MA_PERIOD} hours")
        print(f"   Line widths: ratio={self.RATIO_LINE_WIDTH}, MA={self.MA_LINE_WIDTH} (change at top)")
        print("\n📊 Opening chart window now... CLOSE the window to exit the program.")

        plt.show()   # ← This shows the chart AND pauses the script
        plt.close()


# ====================== RUN THE CLASS ======================
if __name__ == "__main__":
    chart = PriceRatioChart()
    chart.run()
