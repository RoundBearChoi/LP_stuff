from decimal import Decimal
from web3 import Web3

class BaseBalanceChecker:
    # =====================
    # CONFIG (don't change these)
    # =====================
    CBBTC_ADDRESS = "0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf"   # Official cbBTC on Base
    WETH_ADDRESS  = "0x4200000000000000000000000000000000000006"   # Official WETH on Base (WETH9)

    ERC20_ABI = [
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"}
    ]

    def __init__(self):
        # =====================
        # CONNECT TO BASE + VERIFY
        # =====================
        self.w3 = Web3(Web3.HTTPProvider('https://mainnet.base.org'))   # Official Base RPC

        print("Connecting to Base...")

        if not self.w3.is_connected():
            raise Exception("❌ Failed to connect to Base. Check your internet or try another RPC.")

        chain_id = self.w3.eth.chain_id
        print(f"Connected! Chain ID: {chain_id}")

        if chain_id == 8453:
            print("✅ You are on **Base Mainnet**")
        else:
            raise Exception(f"⚠️ Wrong network! Connected to chain {chain_id} instead of Base (8453)")

    # =====================
    # BALANCE FUNCTIONS - Return pure Decimal (100% accuracy)
    # =====================
    def get_cbbtc_balance(self, wallet_address) -> Decimal:
        """Returns cbBTC balance as Decimal (exact precision, no float)."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.CBBTC_ADDRESS), 
            abi=self.ERC20_ABI
        )
        decimals = contract.functions.decimals().call()
        raw_balance = contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_address)
        ).call()
        return Decimal(raw_balance) / Decimal(10 ** decimals)

    def get_eth_balance(self, wallet_address) -> Decimal:
        """Returns native ETH balance as Decimal (exact 18 decimals)."""
        raw_balance_wei = self.w3.eth.get_balance(
            Web3.to_checksum_address(wallet_address)
        )
        return Decimal(raw_balance_wei) / Decimal(10 ** 18)

    def get_weth_balance(self, wallet_address) -> Decimal:
        """Returns WETH balance as Decimal (exact 18 decimals)."""
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(self.WETH_ADDRESS), 
            abi=self.ERC20_ABI
        )
        decimals = contract.functions.decimals().call()
        raw_balance = contract.functions.balanceOf(
            Web3.to_checksum_address(wallet_address)
        ).call()
        return Decimal(raw_balance) / Decimal(10 ** decimals)

    # =====================
    # FORMATTING HELPER
    # =====================
    def _format_decimal(self, value: Decimal, decimal_places: int) -> str:
        """Internal helper: forces clean decimal string (no scientific E-notation).
        Keeps 100% Decimal accuracy - just prettier printing."""
        quantizer = Decimal('1') / (Decimal('10') ** decimal_places)
        quantized = value.quantize(quantizer)
        return f"{quantized:f}"

    # =====================
    # CLEANUP + CONFIRMATION
    # =====================
    def close(self):
        """Properly disconnect (if available) and always show confirmation"""
        if hasattr(self.w3, 'provider') and hasattr(self.w3.provider, 'disconnect'):
            self.w3.provider.disconnect()
        
        print("Disconnected from Base RPC")

    # =====================
    # RUN (user prompt)
    # =====================
    def run(self):
        print('')
        wallet_address = input("Enter your Base wallet address: ").strip()
        
        if not wallet_address:
            print("No address entered.")
            return
        
        try:
            eth_balance   = self.get_eth_balance(wallet_address)
            weth_balance  = self.get_weth_balance(wallet_address)
            cbbtc_balance = self.get_cbbtc_balance(wallet_address)
            
            print(f"\n✅ ETH Balance   : {self._format_decimal(eth_balance, 18)} ETH")
            print(f"✅ WETH Balance  : {self._format_decimal(weth_balance, 18)} WETH")
            print(f"✅ cbBTC Balance : {self._format_decimal(cbbtc_balance, 8)} cbBTC")
        except Exception as e:
            print(f"❌ Error checking balance: {str(e)}")


if __name__ == "__main__":
    checker = BaseBalanceChecker()
    checker.run()
    checker.close()
