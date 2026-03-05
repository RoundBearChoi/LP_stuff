import csv
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Import our existing modules (must be in the same folder)
from get_base_balance import BaseBalanceChecker
from get_market_prices import CoinGeckoPrices


class WalletRecorder:
    """Clean class version of the wallet recorder.
    Works exactly like the previous script — same prompts, same output, same CSV."""

    CSV_FILENAME = "wallet_records.csv"

    def __init__(self):
        self.balance_checker = BaseBalanceChecker()
        self.price_fetcher = CoinGeckoPrices()

    @staticmethod
    def get_kst_now() -> str:
        """Return current time in KST (Korea Standard Time)"""
        kst = timezone(timedelta(hours=9))
        return datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")

    def _calculate_btc_equivalent(
        self,
        eth_balance: Decimal,
        weth_balance: Decimal,
        cbbtc_balance: Decimal,
        btc_price: float | None,
        eth_price: float | None,
    ) -> str:
        """Calculate total portfolio in BTC terms (cbBTC 1:1 + ETH/WETH converted)."""
        total_eth = eth_balance + weth_balance

        if btc_price and eth_price and btc_price > 0:
            eth_in_btc = total_eth * Decimal(str(eth_price)) / Decimal(str(btc_price))
            btc_equivalent = cbbtc_balance + eth_in_btc
            return f"{btc_equivalent:.8f}"
        return "N/A"

    def run(self):
        """Main execution — identical UX to before"""
        print("🔍 Base Wallet Recorder (with BTC-Equivalent)\n")

        wallet_address = input("Enter your Base wallet address: ").strip()
        if not wallet_address:
            print("❌ No address provided.")
            return

        try:
            print("\n📡 Fetching balances from Base + prices from CoinGecko...")

            # === Fetch Balances (exact Decimal precision) ===
            eth_balance: Decimal = self.balance_checker.get_eth_balance(wallet_address)
            weth_balance: Decimal = self.balance_checker.get_weth_balance(wallet_address)
            cbbtc_balance: Decimal = self.balance_checker.get_cbbtc_balance(wallet_address)

            # === Fetch Prices ===
            prices = self.price_fetcher.get_all_prices()
            btc_price = prices.get("btc")
            eth_price = prices.get("eth")

            # === Timestamp + BTC Equivalent ===
            timestamp_kst = self.get_kst_now()
            btc_equiv_str = self._calculate_btc_equivalent(
                eth_balance, weth_balance, cbbtc_balance, btc_price, eth_price
            )

            # === Prepare row for CSV ===
            row = {
                "timestamp_kst": timestamp_kst,
                "wallet_address": wallet_address,
                "eth_balance": str(eth_balance),
                "weth_balance": str(weth_balance),
                "cbbtc_balance": str(cbbtc_balance),
                "btc_price_usd": f"{btc_price:,.2f}" if btc_price is not None else "N/A",
                "eth_price_usd": f"{eth_price:,.2f}" if eth_price is not None else "N/A",
                "btc-equivalent": btc_equiv_str,
            }

            # === Append to CSV (create file + header on first run) ===
            file_exists = os.path.isfile(self.CSV_FILENAME)
            with open(self.CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if not file_exists:
                    writer.writeheader()
                    print(f"📁 Created new file → {self.CSV_FILENAME}")
                writer.writerow(row)

            # === Pretty summary (exactly the same as before) ===
            print("\n" + "═" * 80)
            print(f"✅ SUCCESSFULLY RECORDED — {timestamp_kst}")
            print(f"Wallet         : {wallet_address}")
            print(f"ETH            : {float(eth_balance):,.8f} ETH")
            print(f"WETH           : {float(weth_balance):,.8f} WETH")
            print(f"cbBTC          : {float(cbbtc_balance):,.8f} cbBTC")
            print("-" * 80)
            print(f"BTC Price      : ${btc_price:,.2f}" if btc_price is not None else "BTC Price      : ❌ Failed")
            print(f"ETH Price      : ${eth_price:,.2f}" if eth_price is not None else "ETH Price      : ❌ Failed")
            print(f"BTC-Equivalent : {btc_equiv_str} BTC")
            print("═" * 80)
            print(f"💾 Data saved to: {self.CSV_FILENAME} (same folder as this script)")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}")

    def close(self):
        """Properly disconnect Base RPC"""
        if hasattr(self, "balance_checker") and self.balance_checker:
            self.balance_checker.close()


if __name__ == "__main__":
    recorder = WalletRecorder()
    try:
        recorder.run()
    finally:
        recorder.close()
