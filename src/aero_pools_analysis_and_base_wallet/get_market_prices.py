import requests
from typing import Optional, Dict


class CoinGeckoPrices:
    """
    Simple CoinGecko price fetcher.
    - One API call for all coins
    - Always returns fresh prices
    - Automatic 429 retry
    """
    
    def _fetch_all_prices(self) -> Dict[str, Optional[float]]:
        """Internal: fetch all 4 prices in ONE request"""
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,coinbase-wrapped-btc,weth",
            "vs_currencies": "usd"
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "btc":   data.get("bitcoin",              {}).get("usd"),
                "eth":   data.get("ethereum",             {}).get("usd"),
                "cbbtc": data.get("coinbase-wrapped-btc", {}).get("usd"),
                "weth":  data.get("weth",                 {}).get("usd"),
            }

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print("⏳ Rate limit hit. Waiting 2 seconds and retrying...")
                time.sleep(2)
                return self._fetch_all_prices()  # retry once
            print(f"❌ HTTP error: {e}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

        # Safe defaults on failure
        return {"btc": None, "eth": None, "cbbtc": None, "weth": None}

    # ===================== PUBLIC METHODS =====================
    def get_btc_price(self) -> Optional[float]:
        return self._fetch_all_prices().get("btc")

    def get_eth_price(self) -> Optional[float]:
        return self._fetch_all_prices().get("eth")

    def get_cbbtc_price(self) -> Optional[float]:
        return self._fetch_all_prices().get("cbbtc")

    def get_weth_price(self) -> Optional[float]:
        return self._fetch_all_prices().get("weth")

    def get_all_prices(self) -> Dict[str, Optional[float]]:
        return self._fetch_all_prices()


# ========================= EXAMPLE USAGE =========================
if __name__ == "__main__":
    cg = CoinGeckoPrices()

    prices = cg.get_all_prices()

    print(f"BTC   Price : ${prices['btc']:,.2f}"   if prices['btc']   is not None else "BTC   Price : ❌ Failed")
    print(f"ETH   Price : ${prices['eth']:,.2f}"   if prices['eth']   is not None else "ETH   Price : ❌ Failed")
    print(f"cbBTC Price : ${prices['cbbtc']:,.2f}" if prices['cbbtc'] is not None else "cbBTC Price : ❌ Failed")
    print(f"WETH  Price : ${prices['weth']:,.2f}"  if prices['weth']  is not None else "WETH  Price : ❌ Failed")
