import requests
from typing import Optional


class CryptoRatioFetcher:
    BASE_URL = "https://api.coingecko.com/api/v3/simple/price"
    

    def __init__(self, timeout: int = 10):
        self.timeout = timeout


    def get_btc_eth_ratio(self) -> float:
        """
        Returns BTC price ÷ ETH price (the BTC/ETH ratio).
        Example: ~0.0523 means 1 BTC ≈ 0.0523 ETH (or 1 ETH ≈ 19.12 BTC)
        """
        params = {
            "ids": "bitcoin,ethereum",
            "vs_currencies": "usd",          # CoinGecko needs a fiat currency
            "include_24hr_change": "false"   # we only need spot prices
        }
        
        response = requests.get(
            self.BASE_URL,
            params=params,
            timeout=self.timeout
        )
        response.raise_for_status()  # raises nicely on 4xx/5xx
        
        data = response.json()
        
        btc_price = data["bitcoin"]["usd"]
        eth_price = data["ethereum"]["usd"]
        
        ratio = btc_price / eth_price
        return ratio


if __name__ == "__main__":
    fetcher = CryptoRatioFetcher()
    
    try:
        ratio = fetcher.get_btc_eth_ratio()
        print(f"Current BTC/ETH ratio: {ratio:.6f}")
        print(f"   → 1 BTC  = {ratio:.4f} ETH")
        print(f"   → 1 ETH  = {1/ratio:.4f} BTC")
    except requests.RequestException as e:
        print(f"Error fetching prices: {e}")
