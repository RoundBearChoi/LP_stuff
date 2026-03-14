import sys
import pandas as pd
import matplotlib.pyplot as plt
from config import DEFAULT_CSV_FILE, DEFAULT_CHART_MONTHS as DEFAULT_MAX_MONTHS #separate months vs other scripts

class PriceRatioChart:
    """Clean, reusable class to generate price ratio charts from your CSV."""

    # ==================== CSV + TIMEFRAME (FROM CONFIG) ====================
    CSV_FILE = DEFAULT_CSV_FILE
    MAX_MONTHS = DEFAULT_MAX_MONTHS
    # =====================================================================

    # ==================== TUNABLE SETTINGS ====================
    MA_PERIOD = 168
    RSI_PERIOD = 14
    BAND_MULTIPLIER = 2.4
    RATIO_LINE_WIDTH = 1
    MA_LINE_WIDTH = 2.4
    # =========================================================

    def __init__(self):
        print(f"📁 Using CSV: {self.CSV_FILE}")
        print(f"⏳ Timeframe: last {self.MAX_MONTHS} months "
              f"(0 = full history)")

    def parse_arguments(self):
        if len(sys.argv) == 3:
            symbol1 = sys.argv[1].upper().strip()
            symbol2 = sys.argv[2].upper().strip()
            print(f"Generating ratio chart for {symbol1} / {symbol2}")
            return symbol1, symbol2
        else:
            print("No symbols provided → defaulting to BTC / ETH")
            return 'BTC', 'ETH'

    def calculate_rsi(self, series):
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=self.RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.RSI_PERIOD).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def run(self):
        symbol1, symbol2 = self.parse_arguments()

        print(f"Loading {self.CSV_FILE}...")
        df = pd.read_csv(self.CSV_FILE)

        df['symbol'] = df['symbol'].astype(str).str.upper()
        df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
        df = df.dropna(subset=['datetime', 'close'])

        df1 = df[df['symbol'] == symbol1].copy()
        df2 = df[df['symbol'] == symbol2].copy()

        if df1.empty or df2.empty:
            print(f"❌ One or both symbols not found.")
            sys.exit(1)

        merged = pd.merge(
            df1[['datetime', 'close']],
            df2[['datetime', 'close']],
            on='datetime',
            how='inner',
            suffixes=(f'_{symbol1}', f'_{symbol2}')
        )

        if len(merged) == 0:
            print("❌ No overlapping data.")
            sys.exit(1)

        merged['ratio'] = merged[f'close_{symbol1}'] / merged[f'close_{symbol2}']

        # ==================== TIMEFRAME FILTER ====================
        original_rows = len(merged)
        if self.MAX_MONTHS > 0:
            cutoff = merged['datetime'].max() - pd.DateOffset(months=self.MAX_MONTHS)
            merged = merged[merged['datetime'] >= cutoff].copy().reset_index(drop=True)
            print(f"⏳ Filtered to last {self.MAX_MONTHS} months")
            print(f"   Rows: {original_rows:,} → {len(merged):,}")
        else:
            print("ℹ️ Showing full history")

        # ==================== CALCULATIONS ====================
        print(f"Calculating {self.MA_PERIOD}h MA + RSI + ±{self.BAND_MULTIPLIER}σ bands...")
        merged['rsi'] = self.calculate_rsi(merged['ratio'])
        merged['ma'] = merged['ratio'].rolling(window=self.MA_PERIOD).mean()
        merged['std'] = merged['ratio'].rolling(window=self.MA_PERIOD).std()
        merged['upper_band'] = merged['ma'] + self.BAND_MULTIPLIER * merged['std']
        merged['lower_band'] = merged['ma'] - self.BAND_MULTIPLIER * merged['std']

        merged = merged.dropna(subset=['rsi', 'ma', 'std']).reset_index(drop=True)

        # ==================== FILENAME WITH TIMEFRAME ====================
        months_str = f"{self.MAX_MONTHS}m" if self.MAX_MONTHS > 0 else "full"
        save_name = f"ratio_{symbol1}_{symbol2}_{months_str}.png"

        # ==================== PLOT ====================
        fig, ax = plt.subplots(figsize=(14, 7))
        x = merged['datetime']
        y = merged['ratio']
        ma = merged['ma']
        rsi = merged['rsi']

        # Red bands
        ax.plot(x, merged['upper_band'], color='#e63939', linewidth=1.1, linestyle='--',
                alpha=0.68, label=f'+{self.BAND_MULTIPLIER}σ')
        ax.plot(x, merged['lower_band'], color='#e63939', linewidth=1.1, linestyle='--',
                alpha=0.68, label=f'-{self.BAND_MULTIPLIER}σ')

        # Raw ratio
        ax.plot(x, y, label=f'{symbol1}/{symbol2} Ratio',
                color='#0189FB', linewidth=self.RATIO_LINE_WIDTH, alpha=0.82)

        # RSI-colored MA
        for i in range(1, len(merged)):
            if rsi.iloc[i] > 70:      color = '#e63939'
            elif rsi.iloc[i] > 60:    color = '#f77f00'
            elif rsi.iloc[i] < 30:    color = '#2a9d8e'
            elif rsi.iloc[i] < 40:    color = '#52b788'
            else:                     color = '#006400'
            ax.plot(x.iloc[i-1:i+1], ma.iloc[i-1:i+1], color=color, linewidth=self.MA_LINE_WIDTH)

        ax.set_title(f'Price Ratio: {symbol1} ÷ {symbol2}   |   '
                     f'{self.MA_PERIOD}h MA + ±{self.BAND_MULTIPLIER}σ Bands\n'
                     f'Last {self.MAX_MONTHS if self.MAX_MONTHS > 0 else "ALL"} months • '
                     f'{merged["datetime"].min().strftime("%Y-%m-%d")} → '
                     f'{merged["datetime"].max().strftime("%Y-%m-%d")}',
                     fontsize=16, fontweight='bold')

        ax.set_xlabel('Date (Hourly)')
        ax.set_ylabel(f'{symbol1} / {symbol2} Ratio')
        ax.grid(True, alpha=0.3)
        ax.legend()

        plt.xticks(rotation=45)
        plt.tight_layout()

        # ==================== SAVE (NO SHOW) ====================
        plt.savefig(save_name, dpi=200, bbox_inches='tight')
        plt.close()   # clean up memory

        print("\n✅ SUCCESS!")
        print(f"   Saved: {save_name}")
        print(f"   Points: {len(merged):,} hourly")
        print(f"   Timeframe: {months_str}")
        print(f"   CSV used: {self.CSV_FILE}")


if __name__ == "__main__":
    chart = PriceRatioChart()
    chart.run()
