import sys
import pandas as pd
import matplotlib.pyplot as plt
from config import DEFAULT_CSV_FILE   # ← NEW: now comes from config.json

class PriceRatioChart:
    """Clean, reusable class to generate price ratio charts from your CSV."""

    # ==================== CSV SOURCE (NOW FROM CONFIG) ====================
    CSV_FILE = DEFAULT_CSV_FILE         # Loaded from config.json → "default_csv_file"
    # =====================================================================

    # ==================== TUNABLE SETTINGS (change these only) ====================
    MA_PERIOD = 168                     # hours (168 = 7 days)
    RSI_PERIOD = 14
    BAND_MULTIPLIER = 2.4               # σ multiplier for red bands (2.0 = classic)
    RATIO_LINE_WIDTH = 1
    MA_LINE_WIDTH = 2.4
    # =============================================================================

    def __init__(self):
        """Initialize with default settings."""
        print(f"📁 Using CSV file from config: {self.CSV_FILE}")

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
        """Main execution flow — now with clean red Bollinger Bands."""
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

        if df1.empty or df2.empty:
            print(f"❌ One or both symbols not found in the CSV.")
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

        # ====================== CALCULATE MA + RSI + BANDS ======================
        print(f"Calculating {self.MA_PERIOD}-hour MA + RSI({self.RSI_PERIOD}) + ±{self.BAND_MULTIPLIER}σ Bands...")
        merged['rsi'] = self.calculate_rsi(merged['ratio'])
        merged['ma'] = merged['ratio'].rolling(window=self.MA_PERIOD).mean()
        merged['std'] = merged['ratio'].rolling(window=self.MA_PERIOD).std()
        merged['upper_band'] = merged['ma'] + self.BAND_MULTIPLIER * merged['std']
        merged['lower_band'] = merged['ma'] - self.BAND_MULTIPLIER * merged['std']

        # Drop early NaNs from rolling calculations
        merged = merged.dropna(subset=['rsi', 'ma', 'std']).reset_index(drop=True)

        print(f"Plotting {len(merged):,} points with RSI coloring + red bands...")

        # ====================== CREATE CHART ======================
        fig, ax = plt.subplots(figsize=(14, 7))

        x = merged['datetime']
        y = merged['ratio']
        ma = merged['ma']
        rsi = merged['rsi']

        # 1. Red Bollinger Bands (plotted first so they sit in background)
        ax.plot(x, merged['upper_band'], color='#e63939', linewidth=1.1,
                linestyle='--', alpha=0.68, label=f'+{self.BAND_MULTIPLIER}σ')
        ax.plot(x, merged['lower_band'], color='#e63939', linewidth=1.1,
                linestyle='--', alpha=0.68, label=f'-{self.BAND_MULTIPLIER}σ')

        # 2. Thinner neutral raw ratio line (background)
        ax.plot(x, y,
                label=f'{symbol1} / {symbol2} Ratio',
                color='#0189FB', linewidth=self.RATIO_LINE_WIDTH, alpha=0.82)

        # 3. Thinner RSI-colored MA line (the star — on top)
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

        ax.set_title(f'Price Ratio: {symbol1} ÷ {symbol2}   |   '
                     f'{self.MA_PERIOD}h MA + ±{self.BAND_MULTIPLIER}σ Bands (RSI-colored MA)\n'
                     f'{merged["datetime"].min().strftime("%Y-%m-%d %H:%M")} → '
                     f'{merged["datetime"].max().strftime("%Y-%m-%d %H:%M")}',
                     fontsize=16, fontweight='bold')

        ax.set_xlabel('Date (Hourly)', fontsize=12)
        ax.set_ylabel(f'{symbol1} / {symbol2} Ratio', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)

        plt.xticks(rotation=45)
        plt.tight_layout()

        # ====================== SAVE + SHOW & PAUSE ======================
        save_name = f"ratio_{symbol1}_{symbol2}.png"
        plt.savefig(save_name, dpi=200, bbox_inches='tight')
        
        print("\n✅ SUCCESS! Chart saved AND displayed.")
        print(f"   File: {save_name}")
        print(f"   Data points: {len(merged):,} hourly candles")
        print(f"   MA period: {self.MA_PERIOD} hours")
        print(f"   Bands: ±{self.BAND_MULTIPLIER} standard deviations (red dashed)")
        print(f"   Line widths: ratio={self.RATIO_LINE_WIDTH}, MA={self.MA_LINE_WIDTH} (change at top)")
        print(f"   CSV used: {self.CSV_FILE}")
        print("\n📊 Opening chart window now... CLOSE the window to exit the program.")

        plt.show()   # ← This shows the chart AND pauses the script
        plt.close()


# ====================== RUN THE CLASS ======================
if __name__ == "__main__":
    chart = PriceRatioChart()
    chart.run()
