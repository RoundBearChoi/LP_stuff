from web3 import Web3
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import time


class VeAeroSupplyAnalyzer:
    """Clean, reusable class for fetching & charting Aerodrome veAero historic supply."""

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
        print("   d = Daily   (fine detail, ~950 points)")
        print("   w = Weekly  (recommended — clean long-term trends, ~135 points)")
        print("   m = Monthly (ultra clean overview)")
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

        erc20_abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                      "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}]
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
            if block < 2_000_000:
                break

            try:
                locked_raw = self.call_with_retry(self.aero_contract.functions.balanceOf(self.VE_ADDRESS), block)
                ve_raw = self.call_with_retry(self.ve_contract.functions.totalSupply(), block)
                block_info = self.w3.eth.get_block(block)

                locked_aero = locked_raw / 1e18
                ve_supply = ve_raw / 1e18
                date = datetime.fromtimestamp(block_info['timestamp'])

                data.append({
                    'date': date,
                    'block': block,
                    'total_locked_aero': round(locked_aero, 2),
                    've_voting_supply': round(ve_supply, 2)
                })

                if i % 25 == 0 or i == self.NUM_POINTS - 1:
                    print(f"✅ {i+1:3d} points | {date.strftime('%Y-%m-%d')} | "
                          f"Locked AERO: {locked_aero:,.0f} | veSupply: {ve_supply:,.0f}")

                time.sleep(self.BASE_SLEEP)

            except Exception as e:
                print(f"⚠️ Error at block {block}: {e}")
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
        color1 = '#1f77b4'
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Total Locked AERO', color=color1)
        ax1.plot(self.df['date'], self.df['total_locked_aero'], color=color1, linewidth=3.5, label='Total Locked AERO')
        ax1.tick_params(axis='y', labelcolor=color1)

        ax2 = ax1.twinx()
        color2 = '#ff7f0e'
        ax2.set_ylabel('veAERO Voting Power', color=color2)
        ax2.plot(self.df['date'], self.df['ve_voting_supply'], color=color2, linewidth=3, linestyle='--',
                 label='veAERO Voting Power')
        ax2.tick_params(axis='y', labelcolor=color2)

        plt.title(f'Aerodrome Finance — Historic veAero Supply ({self.days}-day intervals)\n'
                  f'Total Locked AERO vs Voting Power', fontsize=18, pad=20)
        fig.tight_layout()
        ax1.grid(True, alpha=0.3)

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

        # SAVE TO PNG (no window popup)
        plt.savefig(f"{filename_base}.png", dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Chart saved → {filename_base}.png")

    def print_stats(self):
        latest = self.df.iloc[-1]
        print(f"\n📊 CURRENT STATS:")
        print(f"   Total Locked AERO  : {latest['total_locked_aero']:,.0f}")
        print(f"   veAERO Voting Power: {latest['ve_voting_supply']:,.0f}")
        print(f"   Ratio (ve/locked)   : {latest['ve_voting_supply']/latest['total_locked_aero']:.1%}")
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
