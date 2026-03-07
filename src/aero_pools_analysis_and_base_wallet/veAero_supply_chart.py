from web3 import Web3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time


class VeAeroSupplyAnalyzer:
    """Fixed version — crash fixed + better early stopping."""

    AERO_ADDRESS = "0x940181a94A35A4569E4529A3CDfB74e38FD98631"
    VE_ADDRESS = "0xeBf418Fe2512e7E6bd9b87a8F0f294aCDC67e6B4"
    BASE_SLEEP = 0.35
    NUM_POINTS = 800

    def __init__(self):
        self.RPC_URL = None
        self.days = 7
        self.df = None
        self.w3 = None
        self.aero_contract = None
        self.ve_contract = None

    def prompt_alchemy_key(self):
        print("🔑 Aerodrome veAero Historic Supply Chart")
        print("========================================\n")
        print("Get free Alchemy Base Mainnet key at: https://dashboard.alchemy.com/\n")

        alchemy_input = input("Paste your Alchemy API key (or full RPC URL): ").strip()

        if alchemy_input.startswith("https://"):
            self.RPC_URL = alchemy_input
            print("✅ Using full custom RPC URL")
        elif alchemy_input:
            self.RPC_URL = f"https://base-mainnet.g.alchemy.com/v2/{alchemy_input}"
            print("✅ Using Alchemy (fast & reliable)")
        else:
            self.RPC_URL = "https://mainnet.base.org"
            print("⚠️ No key — falling back to public RPC")

        print(f"\nRPC configured: {self.RPC_URL[:50]}...\n")

    def prompt_granularity(self):
        print("📅 Choose data granularity:")
        print("   d = Daily   (fine detail)")
        print("   w = Weekly  (recommended)")
        print("   m = Monthly (clean overview)")
        choice = input("Enter d/w/m [default = w]: ").strip().lower() or "w"

        if choice == "d":
            self.days = 1
            print("✅ Daily granularity selected")
        elif choice == "m":
            self.days = 30
            print("✅ Monthly granularity selected")
        else:
            self.days = 7
            print("✅ Weekly granularity selected (default)")

    def setup_web3(self):
        self.w3 = Web3(Web3.HTTPProvider(self.RPC_URL))
        print("✅ Connected to Base:", self.w3.is_connected())

        erc20_abi = [
            {"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
             "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
            {"constant": True, "inputs": [], "name": "totalSupply",
             "outputs": [{"name": "supply", "type": "uint256"}], "type": "function"}
        ]
        ve_abi = [{"inputs": [], "name": "totalSupply", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                   "stateMutability": "view", "type": "function"}]

        self.aero_contract = self.w3.eth.contract(address=self.AERO_ADDRESS, abi=erc20_abi)
        self.ve_contract = self.w3.eth.contract(address=self.VE_ADDRESS, abi=ve_abi)

        current_block = self.w3.eth.block_number
        print(f"Current block: {current_block:,} | Granularity: {self.days} day(s) per point\n")

    def call_with_retry(self, contract_func, block_id, max_retries=5):
        for attempt in range(max_retries):
            try:
                return contract_func.call(block_identifier=block_id)
            except Exception as e:
                err_str = str(e).upper()
                if "429" in err_str or "TOO MANY REQUESTS" in err_str or "RATE LIMIT" in err_str:
                    wait = min((2 ** attempt) * 3, 25)
                    print(f"⏳ Rate limit at block {block_id} — waiting {wait}s")
                    time.sleep(wait)
                    continue
                else:
                    raise
        raise Exception(f"Failed after {max_retries} retries")

    def fetch_data(self):
        BLOCK_STEP = self.days * 43200
        data = []
        print(f"🚀 Fetching {self.days}-day interval history...\n")

        current_block = self.w3.eth.block_number

        for i in range(self.NUM_POINTS):
            block = current_block - (i * BLOCK_STEP)
            if block < 5_000_000:   # Safe early stop (before contracts existed)
                break

            try:
                locked_raw = self.call_with_retry(self.aero_contract.functions.balanceOf(self.VE_ADDRESS), block)
                total_raw = self.call_with_retry(self.aero_contract.functions.totalSupply(), block)
                ve_raw = self.call_with_retry(self.ve_contract.functions.totalSupply(), block)
                block_info = self.w3.eth.get_block(block)

                locked_aero = locked_raw / 1e18
                total_aero = total_raw / 1e18
                percent_locked = (locked_aero / total_aero * 100) if total_aero > 0 else 0
                ve_supply = ve_raw / 1e18
                date = datetime.fromtimestamp(block_info['timestamp'])

                data.append({
                    'date': date,
                    'block': block,
                    'total_locked_aero': round(locked_aero, 2),
                    'total_aero_supply': round(total_aero, 2),
                    'percent_locked': round(percent_locked, 2),
                    've_voting_supply': round(ve_supply, 2)
                })

                if i % 20 == 0 or i == self.NUM_POINTS - 1:
                    print(f"✅ {i+1:3d} points | {date.strftime('%Y-%m-%d')} | "
                          f"Locked: {locked_aero:,.0f} | Total: {total_aero:,.0f} | "
                          f"% Locked: {percent_locked:.1f}%")

                time.sleep(self.BASE_SLEEP)

            except Exception as e:
                print(f"⚠️ Error at block {block}: {str(e)[:80]}...")
                time.sleep(2)
                continue

        self.df = pd.DataFrame(data).sort_values('date').reset_index(drop=True)
        print(f"\n🎉 Fetched {len(self.df)} clean points from {self.df['date'].min().date()} to today!")

    def save_data(self):
        filename_base = f"veaero_historic_supply_{self.days}day"
        self.df.to_csv(f"{filename_base}.csv", index=False)
        print(f"📁 Data saved → {filename_base}.csv")

    def create_and_save_chart(self):
        filename_base = f"veaero_historic_supply_{self.days}day"

        fig, ax1 = plt.subplots(figsize=(15, 8))
        color_locked = '#1f77b4'
        color_total = '#2ca02c'
        color_percent = '#d62728'

        ax1.set_xlabel('Date')
        ax1.set_ylabel('AERO Supply', color='black')
        ax1.plot(self.df['date'], self.df['total_locked_aero'], color=color_locked, linewidth=3.5, label='Total Locked AERO')
        ax1.plot(self.df['date'], self.df['total_aero_supply'], color=color_total, linewidth=3.0, label='Total AERO Supply')
        ax1.tick_params(axis='y', labelcolor='black')

        ax2 = ax1.twinx()
        ax2.set_ylabel('% of Supply Locked', color=color_percent)
        ax2.plot(self.df['date'], self.df['percent_locked'], color=color_percent, linewidth=3, linestyle='--',
                 label='% of Supply Locked')
        ax2.tick_params(axis='y', labelcolor=color_percent)
        ax2.set_ylim(0, 100)

        plt.title(f'Aerodrome Finance — Historic Supply ({self.days}-day intervals)\n'
                  f'Total AERO Supply vs Locked AERO vs % Locked', fontsize=18, pad=20)
        fig.tight_layout()
        ax1.grid(True, alpha=0.3)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        plt.savefig(f"{filename_base}.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Chart saved → {filename_base}.png")

    def print_stats(self):
        latest = self.df.iloc[-1]
        ve = latest['ve_voting_supply']
        locked = latest['total_locked_aero']
        ratio = (ve / locked * 100) if locked > 0 else 0

        print(f"\n📊 CURRENT STATS:")
        print(f"   Total AERO Supply      : {latest['total_aero_supply']:,.0f}")
        print(f"   Total Locked AERO      : {locked:,.0f}")
        print(f"   % of supply locked     : {latest['percent_locked']:.1f}%")
        print(f"   veAERO Voting Power    : {ve:,.0f}")
        print(f"   ve/locked ratio        : {ratio:.1f}%")
        print(f"   Granularity: {self.days} days | Files saved! 📈")

    def run(self):
        self.prompt_alchemy_key()
        self.prompt_granularity()
        self.setup_web3()
        self.fetch_data()
        self.save_data()
        self.create_and_save_chart()
        self.print_stats()


if __name__ == "__main__":
    analyzer = VeAeroSupplyAnalyzer()
    analyzer.run()
