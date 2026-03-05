import math
from web3 import Web3


# Uniswap V3 pool details (on BASE chain, not Ethereum mainnet)
POOL_ADDRESS = "0x8c7080564B5A792A33Ef2FD473fbA6364d5495e5"
WETH_DECIMALS = 18
CBBTC_DECIMALS = 8

# Public Base RPC (official; alternatives if rate-limited: "https://base-mainnet.public.blastapi.io", "https://rpc.ankr.com/base", or your own Alchemy/Infura Base endpoint)
RPC_URL = "https://mainnet.base.org"

# Minimal ABI for slot0()
SLOT0_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
            {"internalType": "uint16", "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16", "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8", "name": "feeProtocol", "type": "uint8"},
            {"internalType": "bool", "name": "unlocked", "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_bounds(prompt: str = 'enter a number: ') -> float:
    user_input = input(prompt).strip()  # remove leading/trailing whitespace
    has_percent = '%' in user_input     # check if % was present anywhere
    cleaned_input = user_input.replace('%', '').strip()  # remove all % symbols
    
    try:
        number = float(cleaned_input)
        if has_percent:
            number /= 100.0                 # convert percentage to decimal
        return abs(number)                  # always return absolute value
    except ValueError:
        print('invalid input.. returning 0.0001')
        return 0.0001


def get_current_price(verbose: bool = True):
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        raise ConnectionError("Failed to connect to Base node")
   
    pool = w3.eth.contract(address=POOL_ADDRESS, abi=SLOT0_ABI)
    sqrt_price_x96, tick, _, _, _, _, _ = pool.functions.slot0().call()
   
    sqrt_price = sqrt_price_x96 / (2 ** 96)
    raw_price = sqrt_price ** 2  # token1 (cbBTC) per token0 (WETH), in raw units
    adjustment = 10 ** (CBBTC_DECIMALS - WETH_DECIMALS)
    current_price = adjustment / raw_price  # Human-readable: WETH per cbBTC

    if verbose:
        print('')
        print("=== Price Calculation Steps ===")
        print(f"1. sqrtPriceX96 from chain: {sqrt_price_x96}")
        print(f"2. sqrtPrice (divided by 2**96): {sqrt_price:.12f}")
        print(f"3. Raw price squared (cbBTC per WETH, undecimated): {raw_price:.12f}")
        print(f"4. Decimals adjustment: 10**({CBBTC_DECIMALS} - {WETH_DECIMALS}) = {adjustment}")
        print(f"5. Final price (WETH per 1 cbBTC): {current_price:.10f}")
        print(f"   → This means 1 cbBTC currently costs ~{current_price:.10f} WETH\n")

    return current_price


def calculate_required_weth(
    current_price: float,
    lower_pct: float = -0.04,  # -4%
    upper_pct: float = 0.04,   # +4%
    amount_cbbtc: float = 1.0,
    verbose: bool = True
) -> float:
    lower_price = current_price * (1 + lower_pct)
    upper_price = current_price * (1 + upper_pct)
   
    if lower_price >= current_price or upper_price <= current_price:
        raise ValueError("Invalid range")
   
    sqrt_current = math.sqrt(current_price)
    sqrt_lower = math.sqrt(lower_price)
    sqrt_upper = math.sqrt(upper_price)
   
    # Liquidity from cbBTC side (token1)
    delta_y = 1 / sqrt_current - 1 / sqrt_upper
    liquidity = amount_cbbtc / delta_y
   
    # Required WETH from that liquidity (token0)
    delta_x = sqrt_current - sqrt_lower
    required_weth = liquidity * delta_x
   
    if verbose:
        print('')
        print("=== Liquidity Range Calculation Steps ===")
        print(f"Target range: {lower_pct*100:+.1f}% to {upper_pct*100:+.1f}% around current price")
        print(f"→ Lower price bound: {lower_price:.10f} WETH per cbBTC")
        print(f"→ Upper price bound: {upper_price:.10f} WETH per cbBTC\n")
        
        print(f"sqrt(lower):   {sqrt_lower:.10f}")
        print(f"sqrt(current): {sqrt_current:.10f}")
        print(f"sqrt(upper):   {sqrt_upper:.10f}\n")
        
        print(f"cbBTC side delta (Δy = 1/√P_current - 1/√P_upper): {delta_y:.12f}")
        print(f"→ Liquidity L = amount_cbBTC / Δy = {amount_cbbtc} / {delta_y:.12f} = {liquidity:.10f}\n")
        
        print(f"WETH side delta (Δx = √P_current - √P_lower): {delta_x:.12f}")
        print(f"→ Required WETH = L × Δx = {liquidity:.10f} × {delta_x:.12f} = {required_weth:.10f}\n")
        
        ratio = required_weth / amount_cbbtc
        print(f"Final ratio for the position:")
        print(f"   1 cbBTC : {required_weth:.10f} WETH")

    return required_weth


def get_pool_rate(verbose: bool = False) -> float:
    try:
        current_price = get_current_price(verbose=verbose)
      
        print('')
        lower_bound = get_bounds('enter lower bound: ') * -1
        print(f'lower bound set: {lower_bound}')
        print('')
        upper_bound = get_bounds('enter upper bound: ')
        print(f'upper bound set: {upper_bound}')

        required_weth = calculate_required_weth(current_price=current_price,
                                                lower_pct=lower_bound,
                                                upper_pct=upper_bound,
                                                verbose=verbose)

        return required_weth
       
    except Exception as e:
        print(f"Error: {e}")
        print("Tip: Public RPCs can be rate-limited or temporarily down. Try a different RPC from the list above, or use your own key from Alchemy/Infura (Base chain).")


# Main execution
if __name__ == "__main__":
    get_pool_rate()
