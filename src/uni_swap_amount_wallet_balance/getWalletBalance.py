import requests
from web3 import Web3
import csv
import os
from datetime import datetime
import pandas as pd  # Added for nice table printing


# Configuration
CSV_FILE = 'base-btc-eth.csv'
RPC_URL = 'https://mainnet.base.org'  # Public Base RPC endpoint
CBBTC_ADDRESS = '0xcbB7C0000aB88B473b1f5aFd9ef808440eed33Bf'  # cbBTC on Base

# Minimal ERC-20 ABI for balanceOf and decimals (only needed for cbBTC)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]


def get_prices():
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch prices from CoinGecko")
    data = response.json()
    return data['bitcoin']['usd'], data['ethereum']['usd']


def get_cbbtc_balance(w3, wallet_address):
    contract = w3.eth.contract(address=Web3.to_checksum_address(CBBTC_ADDRESS), abi=ERC20_ABI)
    decimals = contract.functions.decimals().call()
    raw_balance = contract.functions.balanceOf(Web3.to_checksum_address(wallet_address)).call()
    return raw_balance / (10 ** decimals)


def get_native_eth_balance(w3, wallet_address):
    raw_balance = w3.eth.get_balance(Web3.to_checksum_address(wallet_address))
    return raw_balance / 1e18


def procCSV():
    # Ask for wallet address
    wallet_address = input("What's base address? ").strip()

    if not Web3.is_address(wallet_address):
        print("Invalid Ethereum address. Please try again.")
        return

    # Connect to Base
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Failed to connect to Base RPC. Check your internet or try another RPC.")
        return

    try:
        # Fetch prices
        btc_price, eth_price = get_prices()
        btc_eth_ratio = btc_price / eth_price if eth_price != 0 else 0

        # Fetch balances
        cbbtc_balance = get_cbbtc_balance(w3, wallet_address)
        eth_balance = get_native_eth_balance(w3, wallet_address)

        # Internal ratio: ETH amount divided by cbBTC amount
        internal_ratio = eth_balance / cbbtc_balance if cbbtc_balance != 0 else 0.0

        # Calculate BTC equivalent: cbBTC (already BTC) + native ETH converted to BTC
        eth_to_btc = eth_price / btc_price if btc_price != 0 else 0
        btc_equivalent = cbbtc_balance + (eth_balance * eth_to_btc)

        # Calculate total USD value
        total_usd_value = btc_equivalent * btc_price

        # Current date/time
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M:%S')

        # Prepare row
        row = [
            date_str,
            time_str,
            f"{btc_price:.2f}",
            f"{eth_price:.2f}",
            f"{btc_eth_ratio:.6f}",
            f"{cbbtc_balance:.8f}",
            f"{eth_balance:.8f}",
            f"{internal_ratio:.8f}",      # New column
            f"{btc_equivalent:.8f}",
            f"{total_usd_value:.2f}"
        ]

        # Write to CSV (create with header if new)
        file_exists = os.path.isfile(CSV_FILE)
        with open(CSV_FILE, mode='a', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    'date', 'time', 'btc_price', 'eth_price',
                    'btc_eth_ratio', 'cbbtc_balance', 'eth_balance',
                    'wallet_ratio',
                    'btc_equivalent', 'total_usd_value'
                ])
            writer.writerow(row)
        
        print('')
        print("Data appended to", CSV_FILE)

        # Load CSV and print the most recent 10 entries (or all if fewer)
        df = pd.read_csv(CSV_FILE)
        print("\nRecent entries (up to 10 most recent):")
        print(df.tail(10).to_string(index=False))

        return cbbtc_balance, eth_balance

    except Exception as e:
        print("Error:", str(e))


if __name__ == '__main__':
    cbbtc_balance, eth_balance = procCSV()
