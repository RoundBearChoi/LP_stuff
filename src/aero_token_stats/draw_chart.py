import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import glob
import os


class AeroChart:
    """Clean class for AERO chart with EMA21/EMA50 + auto PNG export.
       Now fully Aerodrome-native and auto-detects latest CSV."""

    def __init__(self, csv_file: str = None):
        if csv_file is None:
            # Auto-find the newest aerodrome CSV (works for 5m, 15m, 1h...)
            aerodrome_files = glob.glob("AERO_*_aerodrome.csv")
            if aerodrome_files:
                self.csv_file = max(aerodrome_files, key=os.path.getmtime)
                print(f"📂 Auto-loaded latest Aerodrome data: {self.csv_file}")
            else:
                # Graceful fallback
                bybit_files = glob.glob("AERO_*_bybit.csv")
                self.csv_file = max(bybit_files, key=os.path.getmtime) if bybit_files else None
                if self.csv_file:
                    print(f"⚠️  No aerodrome CSV found → using old: {self.csv_file}")
                else:
                    raise FileNotFoundError("No AERO_*.csv files found in current folder!")
        else:
            self.csv_file = csv_file
            print(f"📂 Using manually specified file: {self.csv_file}")

        self.df = None
        self.plot_df = None

    def load_data(self):
        """Load and prepare the CSV (unchanged — fully compatible)."""
        self.df = pd.read_csv(self.csv_file)
        self.df['datetime'] = pd.to_datetime(self.df['datetime'])
        self.df = self.df.set_index('datetime')
        self.df = self.df.sort_index()

    def calculate_indicators(self):
        """Add EMA21, EMA50 and crossover signals."""
        self.df['EMA21'] = self.df['close'].ewm(span=21, adjust=False).mean()
        self.df['EMA50'] = self.df['close'].ewm(span=50, adjust=False).mean()
        self.df['Signal'] = np.where(self.df['EMA21'] > self.df['EMA50'], 1, 0)
        self.df['Position'] = self.df['Signal'].diff()

    def plot_and_save(self, days: int = 5):
        """Generate chart + dedicated bottom panel."""
        last_date = self.df.index.max()
        self.plot_df = self.df[self.df.index >= last_date - pd.Timedelta(days=days)]

        plt.figure(figsize=(15, 10.5))

        # Price + EMAs
        ax1 = plt.subplot2grid((5, 1), (0, 0), rowspan=3)
        ax1.plot(self.plot_df['close'], label='Close Price', color='black', linewidth=1.1)
        ax1.plot(self.plot_df['EMA21'], label='EMA 21 (short)', color='#FF9800', linewidth=2)
        ax1.plot(self.plot_df['EMA50'], label='EMA 50 (slightly longer)', color='#2196F3', linewidth=2)

        # Crossovers
        golden = self.plot_df[self.plot_df['Position'] == 1]
        death = self.plot_df[self.plot_df['Position'] == -1]
        ax1.scatter(golden.index, golden['EMA21'], marker='^', color='green', s=120,
                    label='Golden Cross (Bullish)', zorder=5)
        ax1.scatter(death.index, death['EMA21'], marker='v', color='red', s=120,
                    label='Death Cross (Bearish)', zorder=5)

        ax1.set_title(f'AERO Token - 5m Chart with EMA21 & EMA50 (Last {days} Days • Aerodrome Data)')
        ax1.set_ylabel('Price (USD)')
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left')

        # Volume
        ax2 = plt.subplot2grid((5, 1), (3, 0), sharex=ax1)
        ax2.bar(self.plot_df.index, self.plot_df['volume'], color='gray', alpha=0.7)
        ax2.set_ylabel('Volume (USD)')
        ax2.grid(True, alpha=0.3)

        # Bottom info panel
        ax3 = plt.subplot2grid((5, 1), (4, 0))
        ax3.axis('off')

        latest = self.df.iloc[-1]
        latest_time = self.df.index[-1].strftime('%Y-%m-%d %H:%M')
        is_bullish = latest['EMA21'] > latest['EMA50']

        if is_bullish:
            direction = "Bullish"
            strength = "Strong" if latest['close'] > latest['EMA21'] else "Weak"
        else:
            direction = "Bearish"
            strength = "Strong" if latest['close'] < latest['EMA21'] else "Weak"

        full_trend = f"{strength} {direction}"

        text = f"Latest data: {latest_time}\n" \
               f"Latest Close Price : {latest['close']:.4f} USD\n" \
               f"Overall Trend : {full_trend}\n"

        if len(self.df) > 48:
            change_4h = (latest['close'] - self.df.iloc[-49]['close']) / self.df.iloc[-49]['close'] * 100
            text += f"Last 4 hours change: {change_4h:+.2f}%\n"
        if len(self.df) > 289:
            change_24h = (latest['close'] - self.df.iloc[-289]['close']) / self.df.iloc[-289]['close'] * 100
            text += f"Last 24 hours change: {change_24h:+.2f}%"

        ax3.text(0.5, 0.5, text, ha='center', va='center', fontsize=13, fontweight='bold',
                 linespacing=1.5,
                 bbox=dict(boxstyle="round,pad=1.2", facecolor="white", alpha=0.98, edgecolor="#333333"))

        plt.tight_layout()

        filename = f"AERO_{days}day_EMA_chart.png"
        plt.savefig(filename, dpi=150, bbox_inches='tight')
        print(f"✅ Chart saved as: {filename}")
        plt.close()

    def print_analysis(self):
        """Print today's trend summary."""
        latest = self.df.iloc[-1]
        print("\n" + "="*70)
        print("AERO TOKEN - TODAY'S TREND ANALYSIS (Aerodrome Data)")
        print("="*70)
        print(f"Latest Close Price : {latest['close']:.4f} USD")
        print(f"EMA21              : {latest['EMA21']:.4f}")
        print(f"EMA50              : {latest['EMA50']:.4f}")

        is_bullish = latest['EMA21'] > latest['EMA50']
        direction = "Bullish" if is_bullish else "Bearish"
        strength = "Strong" if (latest['close'] > latest['EMA21']) == is_bullish else "Weak"
        print(f"Overall Trend      : {strength} {direction}")

        if len(self.df) > 48:
            change_4h = (latest['close'] - self.df.iloc[-49]['close']) / self.df.iloc[-49]['close'] * 100
            print(f"Last 4 hours change: {change_4h:+.2f}%")
        if len(self.df) > 289:
            change_24h = (latest['close'] - self.df.iloc[-289]['close']) / self.df.iloc[-289]['close'] * 100
            print(f"Last 24 hours change: {change_24h:+.2f}%")
        print("="*70)

    def run(self, days: int = 5):
        """Full workflow in one call."""
        self.load_data()
        self.calculate_indicators()
        self.plot_and_save(days=days)
        self.print_analysis()


# ====================== RUN IT ======================
if __name__ == "__main__":
    chart = AeroChart()          # ← auto-detects newest aerodrome CSV
    chart.run(days=5)            # change to 3, 7, 14 etc. as needed
