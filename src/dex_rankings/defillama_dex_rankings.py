import requests
import pandas as pd
import matplotlib.pyplot as plt
import sys
from datetime import datetime


class DexRankings:
    """DEX Rankings fetcher and visualizer from DefiLlama API."""

    KEY_MAP = {
        1:  ("total24h", "24h"),
        7:  ("total7d",  "7d"),
        30: ("total30d", "30d")
    }

    def __init__(self, days: int = 7):
        self.days = self._validate_days(days)
        self.vol_key, self.period = self.KEY_MAP[self.days]
        self.df = None

    def _validate_days(self, days: int) -> int:
        """Validate CLI argument and default to 7 if invalid."""
        if days not in [1, 7, 30]:
            print("⚠️  Only 1, 7, or 30 supported. Defaulting to 7d")
            return 7
        return days

    def fetch_data(self):
        """Fetch raw DEX data from DefiLlama."""
        print(f"Fetching current top DEXes by {self.period} volume...")

        url = "https://api.llama.fi/overview/dexs"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()

        self.df = pd.DataFrame(data.get("protocols", []))

    def process_data(self):
        """Handle display names, column detection, cleaning & ranking."""
        # Nice display name
        if "displayName" in self.df.columns:
            self.df["display_name"] = self.df["displayName"]
        elif "name" in self.df.columns:
            self.df["display_name"] = self.df["name"]
        else:
            self.df["display_name"] = self.df.index.astype(str)

        # Smart column detection (in case DefiLlama changes again)
        if self.vol_key not in self.df.columns:
            print(f"⚠️  {self.vol_key} not found, checking fallbacks...")
            fallback = f"volume{self.period}"
            if fallback in self.df.columns:
                self.vol_key = fallback
                print(f"   → using fallback {fallback}")
            else:
                vol_cols = [col for col in self.df.columns 
                           if any(x in col.lower() for x in ['total', 'volume'])]
                print(f"   Available volume columns: {vol_cols}")
                if vol_cols:
                    self.vol_key = vol_cols[0]
                    self.period = self.vol_key.replace('total', '').replace('volume', '')
                    print(f"   → auto-selected {self.vol_key}")
                else:
                    raise KeyError("No volume column found in DefiLlama response")

        # Clean & rank (highest volume first → #1 on top in chart)
        self.df = self.df[self.df[self.vol_key] > 0].copy()
        self.df["volume_b"] = self.df[self.vol_key] / 1_000_000_000
        self.df = self.df.sort_values("volume_b", ascending=False).head(15).reset_index(drop=True)

    def print_table(self):
        """Print the ranking table."""
        print(f"\n=== TOP 15 DEXes by {self.period} Trading Volume ===")
        print(self.df[["display_name", "volume_b"]].round(3).to_string(index=False))

    def generate_chart(self):
        """Generate HD-sized horizontal bar chart with #1 on top."""
        plt.figure(figsize=(11, 8))

        bars = plt.barh(self.df["display_name"], self.df["volume_b"],
                        color='#3498db', edgecolor='black', alpha=0.85)

        plt.xlabel(f"{self.period} Trading Volume (Billions USD)", fontsize=12)
        plt.title(f"Top DEXes by {self.period} Volume — {datetime.now().strftime('%B %d, %Y')}",
                  fontsize=14, fontweight='bold', pad=20)

        plt.grid(axis='x', alpha=0.3)
        plt.gca().invert_yaxis()   # ← puts #1 at the very top

        # Value labels on bars
        for bar in bars:
            width = bar.get_width()
            plt.text(width + 0.03, bar.get_y() + bar.get_height()/2,
                     f'{width:.2f}B', va='center', fontsize=10.5, fontweight='medium')

        plt.tight_layout()

        filename = f"top_dexes_{self.period}.png"
        plt.savefig(filename, dpi=250, bbox_inches='tight')
        plt.close()

        print(f"\n✅ Chart saved → {filename}")

    def run(self):
        """Run the full pipeline (fetch → process → table → chart)."""
        self.fetch_data()
        self.process_data()
        self.print_table()
        self.generate_chart()

        print("\nUsage:")
        print("   python dexRankings.py        → 7-day (default)")
        print("   python dexRankings.py 30     → 30-day")
        print("   python dexRankings.py 1      → 24-hour")


# ==================== CLI ENTRY POINT ====================
if __name__ == "__main__":
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print("Usage: python dexRankings.py [1|7|30]")
            sys.exit(1)
    else:
        days = 7

    app = DexRankings(days)
    app.run()
