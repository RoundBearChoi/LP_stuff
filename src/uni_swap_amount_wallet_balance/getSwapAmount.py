from getWalletBalance import procCSV
from marketRate import CryptoRatioFetcher 
from getUniRate import get_pool_rate


def get_swap_amount():
    cbbtc_balance, eth_balance = procCSV()
    print('')
    print(' --- getting swap amount --- ')
    print(f'cbbtc balance: {cbbtc_balance:.8f}')
    print(f'eth balance: {eth_balance:.8f}')

    fetcher = CryptoRatioFetcher()
    market_rate = fetcher.get_btc_eth_ratio()

    print('')
    print(f'market rate: {market_rate}')

    uniswap_rate = get_pool_rate()

    print('')
    print(f'uniswap pool rate: {uniswap_rate:.8f}')

    eth_equi = to_float(eth_balance) + (to_float(cbbtc_balance) * to_float(market_rate))
    target_btc_amount = eth_equi / (to_float(market_rate) + to_float(uniswap_rate))
    target_eth_amount = target_btc_amount * to_float(uniswap_rate)
    btc_delta = target_btc_amount - to_float(cbbtc_balance)
    eth_delta = target_eth_amount - eth_balance

    print('')
    print(' --- swap amount calculation result --- ')
    print(f'eth equivalent: {eth_equi:.8f}')
    print(f'target btc amount: {target_btc_amount:.8f}')
    print(f'target eth amount: {target_eth_amount:.8f}')
    print('')
    print(f'btc_delta: {btc_delta:.8f}')
    print(f'eth_delta: {eth_delta:.8f}')


def to_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# Examples
#print(to_float(None))          # 0.0
#print(to_float(5))             # 5.0
#print(to_float("3.14"))        # 3.14
#print(to_float("invalid"))     # 0.0 (fallback on error)


if __name__ == '__main__':
    get_swap_amount()
