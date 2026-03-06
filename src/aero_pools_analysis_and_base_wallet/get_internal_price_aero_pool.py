import requests
from decimal import Decimal, getcontext, DivisionByZero, InvalidOperation

# Set high precision for calculations involving square roots and divisions
getcontext().prec = 40
getcontext().traps[DivisionByZero] = False    # we'll handle zero cases manually if needed
getcontext().traps[InvalidOperation] = False


class AerodromeRangeCalculator:
    def get_pool_info(self):
        """Fetch live pool data from DexScreener"""
        url = "https://api.dexscreener.com/latest/dex/pairs/base/0x22aee3699b6a0fed71490c103bd4e5f3309891d5"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            pair = data['pair']

            # Convert strings directly to Decimal to avoid float conversion errors
            price_weth = Decimal(str(pair['priceNative']))
            price_usd = Decimal(str(pair.get('priceUsd', '0')))
            liq_usd = Decimal(str(pair['liquidity'].get('usd', '0')))

            print("✅ Live data from DexScreener")
            print(f"   Current price: 1 cbBTC ≈ {price_weth:.8f} WETH  (${price_usd:,.2f})")
            print(f"   Pool liquidity: ~${liq_usd:,.0f} USD\n")

            return price_weth

        except Exception as e:
            print(f"⚠️  Could not fetch live price ({e}). Using manual input.")
            while True:
                try:
                    user_input = input("Enter current WETH per cbBTC price: ").strip()
                    price = Decimal(user_input)
                    if price <= 0:
                        print("Price must be positive.")
                        continue
                    return price
                except Exception:
                    print("Invalid number. Please enter a valid decimal number.")

    def run(self):
        """Main execution flow"""
        P = self.get_pool_info()           # Decimal

        # User input for range percentage
        while True:
            try:
                range_pct_str = input("Enter range % (e.g. 1.2 for ±1.2%): ").strip()
                range_pct = Decimal(range_pct_str)
                if range_pct <= 0:
                    print("Range must be positive.")
                    continue
                break
            except Exception:
                print("Please enter a valid positive number.")

        r = range_pct / Decimal('100')

        one = Decimal('1')
        low = P * (one - r)
        high = P * (one + r)

        # Safety check — prevent invalid ranges
        if low <= 0:
            print("\n⚠️  Warning: lower bound of range is ≤ 0 — this is not a valid range.")
            low = Decimal('0.000000000000000001')  # very small positive number

        print(f"\n📊 WETH-cbBTC Price Range (±{range_pct}%):")
        print(f"   Low     : {low:,.10f} WETH per cbBTC    →  {one / low:.18f} cbBTC per WETH")
        print(f"   Current : {P:,.10f} WETH per cbBTC     →  {one / P:.18f} cbBTC per WETH")
        print(f"   High    : {high:,.10f} WETH per cbBTC    →  {one / high:.18f} cbBTC per WETH")

        # ──────────────────────────────────────────────────────────────
        # Concentrated liquidity math (Uniswap V3 style position sizing)
        # ──────────────────────────────────────────────────────────────
        sqrt_p = P.sqrt()
        sqrt_low = low.sqrt()
        sqrt_high = high.sqrt()

        L = Decimal('1')  # liquidity = 1 (you can scale this later)

        # Amount of token0 (cbBTC) needed when price is inside range
        amount_cbBTC = L * (one / sqrt_p - one / sqrt_high)

        # Amount of token1 (WETH) needed
        amount_WETH = L * (sqrt_p - sqrt_low)

        if amount_cbBTC <= 0 or amount_WETH <= 0:
            print("\n⚠️  Warning: One or both token amounts are zero or negative.")
            print("   This usually means the current price is outside the chosen range.")

        ratio_weth_per_cb = amount_WETH / amount_cbBTC if amount_cbBTC != 0 else Decimal('inf')
        ratio_cb_per_weth = amount_cbBTC / amount_WETH if amount_WETH != 0 else Decimal('inf')

        print(f"\n🔢 Internal Ratio for ±{range_pct}% Range Position (at current price):")
        print(f"   Deposit cbBTC : {amount_cbBTC:,.12f}")
        print(f"   Deposit WETH  : {amount_WETH:,.10f}")
        print(f"   Ratio         : {ratio_weth_per_cb:,.10f} WETH per cbBTC")
        print(f"                   →  {ratio_cb_per_weth:,.18f} cbBTC per WETH")


if __name__ == "__main__":
    calculator = AerodromeRangeCalculator()
    calculator.run()
