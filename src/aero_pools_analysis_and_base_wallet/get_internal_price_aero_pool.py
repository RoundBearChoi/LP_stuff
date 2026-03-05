import requests
import math


class AerodromeRangeCalculator:
    def get_pool_info(self):
        """Fetch live pool data from DexScreener"""
        url = "https://api.dexscreener.com/latest/dex/pairs/base/0x22aee3699b6a0fed71490c103bd4e5f3309891d5"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            pair = data['pair']
            
            price_weth = float(pair['priceNative'])
            price_usd = float(pair.get('priceUsd', 0))
            liq_usd = pair['liquidity'].get('usd', 0)
            
            print(f"✅ Live data from DexScreener")
            print(f"   Current price: 1 cbBTC ≈ {price_weth:.4f} WETH (${price_usd:,.0f})")
            print(f"   Pool liquidity: ~${liq_usd:,.0f} USD\n")
            return price_weth
        except Exception as e:
            print(f"⚠️ Could not fetch live price ({e}). Using manual input.")
            return float(input("Enter current WETH per cbBTC price: "))

    def run(self):
        """Main execution flow — exactly the same behavior as before"""
        # Get current price
        P = self.get_pool_info()

        # User input for range
        range_pct = float(input("Enter range % (e.g. 1.2 for ±1.2%): "))
        r = range_pct / 100.0

        # Calculate price range
        low = P * (1 - r)
        high = P * (1 + r)

        print(f"\n📊 WETH-cbBTC Price Range (±{range_pct}%):")
        print(f"   Low  : {low:.4f} WETH per cbBTC   ({1/low:.6f} cbBTC per WETH)")
        print(f"   High : {high:.4f} WETH per cbBTC   ({1/high:.6f} cbBTC per WETH)")

        # V3-style math for concentrated liquidity position
        sqrt_p = math.sqrt(P)
        sqrt_low = math.sqrt(low)
        sqrt_high = math.sqrt(high)

        L = 1.0

        amount_cbBTC = L * (1 / sqrt_p - 1 / sqrt_high)
        amount_WETH = L * (sqrt_p - sqrt_low)

        ratio_weth_per_cb = amount_WETH / amount_cbBTC
        ratio_cb_per_weth = amount_cbBTC / amount_WETH

        print(f"\n🔢 Internal Ratio for ±{range_pct}% Range Position (at current price):")
        print(f"   Deposit {amount_cbBTC:.6f} cbBTC")
        print(f"   Deposit {amount_WETH:.6f} WETH")
        print(f"   Ratio   : {ratio_weth_per_cb:.2f} WETH per cbBTC")
        print(f"             ({ratio_cb_per_weth:.6f} cbBTC per WETH)")


if __name__ == "__main__":
    calculator = AerodromeRangeCalculator()
    calculator.run()
