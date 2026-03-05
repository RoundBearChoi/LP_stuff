import os
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
from dune_client.client import DuneClient

class MemecoinDashboard:
    QUERY_ID = 4010816
    OUTPUT_FILE = "memecoin_dashboard.png"

    def __init__(self):
        self.dune = self._init_dune_client()
        self.date_col = 'date_time'
        self.platform_col = 'platform'
        self.count_col = 'daily_token_count'
        
        self.df = None
        self.df_ma = None
        self.df_total = None
        self.df_pivot = None
        self.df_share = None
        self.df_pivot_cum = None

    def _init_dune_client(self):
        DUNE_API_KEY = os.getenv("DUNE_API_KEY")
        if not DUNE_API_KEY:
            DUNE_API_KEY = input("🔑 Paste your full Dune API key here: ").strip()
            if not DUNE_API_KEY:
                print("❌ No key entered. Exiting.")
                exit(1)
        return DuneClient(api_key=DUNE_API_KEY)

    def _normalize_platform(self, name):
        name = str(name).strip()
        lower = name.lower()
        if any(x in lower for x in ['raydium', 'launchlab', 'launch lab']):
            return 'Raydium LaunchLab'
        if lower == 'pumpdotfun':
            return 'Pump.fun'
        return name

    def fetch_data(self):
        print(f"\n🔄 Fetching live data from Dune Query #{self.QUERY_ID}...")
        self.df = self.dune.get_latest_result_dataframe(self.QUERY_ID)

        self.df['date'] = pd.to_datetime(
            self.df[self.date_col].astype(str).str.replace(' UTC', ''), 
            errors='coerce'
        )
        self.df = self.df.sort_values('date').dropna(subset=['date'])

        self.df[self.platform_col] = self.df[self.platform_col].apply(self._normalize_platform)

        print("\nLatest 5 rows preview:")
        print(self.df[['date', self.platform_col, self.count_col]].tail(5))

    def compute_metrics(self):
        self.df_ma = (
            self.df.set_index('date')
            .groupby(self.platform_col)[self.count_col]
            .rolling(window=7, min_periods=1)
            .mean()
            .reset_index()
        )

        self.df_total = self.df.groupby('date')[self.count_col].sum().reset_index(name='total_daily')
        self.df_total['ma7'] = self.df_total['total_daily'].rolling(window=7, min_periods=1).mean()

        self.df_pivot = self.df.pivot(
            index='date', 
            columns=self.platform_col, 
            values=self.count_col
        ).fillna(0)

        self.df_share = self.df_pivot.div(self.df_pivot.sum(axis=1), axis=0) * 100
        self.df_pivot_cum = self.df_pivot.cumsum()

    def print_market_share(self):
        print("\n" + "="*90)
        print("               CURRENT MARKET SHARE")
        print("="*90)

        latest_date = self.df['date'].max().date()
        print(f"📅 Data as of: {latest_date}\n")

        seven_days_ago = self.df['date'].max() - pd.Timedelta(days=6)
        recent = self.df[self.df['date'] >= seven_days_ago].copy()
        total_7d = recent[self.count_col].sum()
        share_7d = (recent.groupby(self.platform_col)[self.count_col]
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index())
        share_7d['share_%'] = (share_7d[self.count_col] / total_7d * 100).round(2)
        share_7d = share_7d.rename(columns={self.count_col: 'launches'})

        print(f"LAST 7 DAYS  ({seven_days_ago.date()} → {latest_date})")
        print(f"Total memecoins launched: {total_7d:,}  →  avg {total_7d/7:,.0f}/day\n")
        print(share_7d.to_string(index=False, 
                                columns=['platform', 'launches', 'share_%'],
                                header=['Platform', 'Launches', '% Share']))
        print("-" * 90)

        latest_day = self.df[self.df['date'] == self.df['date'].max()]
        total_day = latest_day[self.count_col].sum()
        share_day = (latest_day.groupby(self.platform_col)[self.count_col]
                     .sum()
                     .sort_values(ascending=False)
                     .reset_index())
        share_day['share_%'] = (share_day[self.count_col] / total_day * 100).round(2)
        share_day = share_day.rename(columns={self.count_col: 'launches'})

        print(f"LATEST 24H ({latest_date})")
        print(f"Total memecoins launched: {total_day:,}\n")
        print(share_day.to_string(index=False, 
                                 columns=['platform', 'launches', 'share_%'],
                                 header=['Platform', 'Launches', '% Share']))

    def generate_dashboard(self):
        today = datetime.now().strftime("%B %d, %Y")

        # Dynamic title: only show platforms that actually have data
        active_platforms = [p for p in self.df[self.platform_col].unique() 
                           if self.df_pivot[p].sum() > 0]
        title_platforms = " • ".join(active_platforms[:4])  # max 4 shown + etc.
        if len(active_platforms) > 4:
            title_platforms += " • etc."

        fig, axs = plt.subplots(2, 2, figsize=(24, 16), dpi=120)

        # Top-left: 7DMA
        for platform in self.df_ma[self.platform_col].unique():
            subset = self.df_ma[self.df_ma[self.platform_col] == platform]
            axs[0, 0].plot(subset['date'], subset[self.count_col], label=platform, linewidth=2.8)
        axs[0, 0].set_title("7-Day MA — Daily Memecoins by Platform", fontsize=16, pad=15)
        axs[0, 0].set_ylabel("Avg Daily Creations", fontsize=12)
        axs[0, 0].legend(title="Platform", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=10)
        axs[0, 0].grid(True, alpha=0.3)

        # Top-right: Total
        axs[0, 1].plot(self.df_total['date'], self.df_total['ma7'], color='purple', linewidth=3.5, label='7-Day MA Total')
        axs[0, 1].plot(self.df_total['date'], self.df_total['total_daily'], color='purple', alpha=0.25, label='Raw Daily Total')
        axs[0, 1].set_title("Total Daily Memecoins Across All Platforms\n(7-Day Moving Average)", fontsize=16, pad=15)
        axs[0, 1].set_ylabel("Avg Daily Creations", fontsize=12)
        axs[0, 1].legend(fontsize=11)
        axs[0, 1].grid(True, alpha=0.3)

        # Bottom-left: Market share (safe ordering)
        priority = ['Pump.fun', 'Raydium LaunchLab']
        existing = list(self.df_share.columns)
        order = [p for p in priority if p in existing]
        remaining = [col for col in existing if col not in order]
        order += remaining
        self.df_share = self.df_share[order]

        colors = {
            'Pump.fun':           '#FF6600',
            'Raydium LaunchLab':  '#39FF14',
            'LetsBonk':           '#8E44FF',
            'Moonshot':           '#FF33CC',
            'Bags':               '#00CCFF',
            'Boop':               '#33FF99',
            'Believeapp':         '#FF1493',
            'Jup Studio':         '#FF4500',
            'Moon.it':            '#A0522D',
            'Wavebreak':          '#FFD700'
        }
        color_list = [colors.get(col, '#555555') for col in self.df_share.columns]

        self.df_share.plot.area(stacked=True, alpha=0.92, linewidth=0.6, ax=axs[1, 0], color=color_list)
        axs[1, 0].set_title("Platform Market Share % — Daily Launches", fontsize=16, pad=15)
        axs[1, 0].set_ylabel("Share of Total (%)", fontsize=12)
        axs[1, 0].legend(title="Platform", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9.5)
        axs[1, 0].grid(True, alpha=0.3)

        # Bottom-right: Cumulative
        self.df_pivot_cum.plot.area(stacked=True, alpha=0.85, linewidth=0.5, ax=axs[1, 1])
        axs[1, 1].set_title("Cumulative Memecoins Created by Platform", fontsize=16, pad=15)
        axs[1, 1].set_ylabel("Total Tokens Deployed", fontsize=12)
        axs[1, 1].legend(title="Platform", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9.5)
        axs[1, 1].grid(True, alpha=0.3)

        fig.suptitle(f"Memecoin Launch Dashboard — {today}\n{title_platforms}",
                     fontsize=22, fontweight='bold', y=0.98)

        plt.tight_layout(rect=[0, 0, 1, 0.94])

        plt.savefig(self.OUTPUT_FILE, dpi=120, bbox_inches='tight', facecolor='white')
        print(f"\n✅ DASHBOARD SAVED → {self.OUTPUT_FILE}  (2880×1920 px)")
        plt.close()

    def run(self):
        self.fetch_data()
        self.compute_metrics()
        self.print_market_share()
        self.generate_dashboard()
        print("\n🚀 Dashboard ready! Open memecoin_dashboard.png")

if __name__ == "__main__":
    dashboard = MemecoinDashboard()
    dashboard.run()
