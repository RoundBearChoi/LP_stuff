import csv
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Import our existing modules (must be in the same folder)
from get_base_balance import BaseBalanceChecker
from get_market_prices import CoinGeckoPrices


class WalletRecorder:
    """Final version: rolling .txt backup + auto-restore + latest 10 entries on console."""

    CSV_FILENAME = "wallet_records.csv"
    BACKUP_TXT = "wallet_records_backup.txt"
    MAX_BACKUP_ENTRIES = 100

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
        """Calculate total portfolio in BTC terms."""
        total_eth = eth_balance + weth_balance

        if btc_price and eth_price and btc_price > 0:
            eth_in_btc = total_eth * Decimal(str(eth_price)) / Decimal(str(btc_price))
            btc_equivalent = cbbtc_balance + eth_in_btc
            return f"{btc_equivalent:.8f}"
        return "N/A"

    # ====================== .TXT BACKUP LOGIC (unchanged) ======================
    def _write_rolling_backup_txt(self, rows: list[dict]):
        try:
            with open(self.BACKUP_TXT, "w", encoding="utf-8") as f:
                f.write("=== WALLET RECORDS BACKUP (Latest 100 Entries) ===\n")
                f.write(f"Last updated: {self.get_kst_now()}\n")
                f.write(f"Entries: {len(rows)} (max {self.MAX_BACKUP_ENTRIES})\n")
                f.write("=" * 60 + "\n\n")
                for i, row in enumerate(rows, 1):
                    f.write(f"=== ENTRY {i:03d} ===\n")
                    for key, value in row.items():
                        f.write(f"{key}={value}\n")
                    f.write("\n")
            print(f"📦 Rolling backup updated → {self.BACKUP_TXT} ({len(rows)} entries)")
        except Exception as e:
            print(f"⚠️ Could not update backup.txt: {e}")

    def _parse_backup_txt(self) -> list[dict]:
        if not os.path.isfile(self.BACKUP_TXT):
            return []
        try:
            entries = []
            current = {}
            with open(self.BACKUP_TXT, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("=== ENTRY"):
                        if current:
                            entries.append(current)
                        current = {}
                    elif "=" in line and not line.startswith("==="):
                        key, value = line.split("=", 1)
                        current[key.strip()] = value.strip()
            if current:
                entries.append(current)
            return entries
        except Exception:
            return []

    def _restore_from_backup(self):
        entries = self._parse_backup_txt()
        if not entries:
            print("⚠️ No backup data available to restore.")
            return
        try:
            with open(self.CSV_FILENAME, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=entries[0].keys())
                writer.writeheader()
                writer.writerows(entries)
            print(f"✅ Restored {len(entries)} entries from backup.txt into {self.CSV_FILENAME}")
        except Exception as e:
            print(f"⚠️ Restore failed: {e}")

    def _load_latest_from_backup(self, wallet_address: str) -> dict | None:
        entries = self._parse_backup_txt()
        for entry in reversed(entries):
            if entry.get("wallet_address", "").lower() == wallet_address.lower():
                return entry
        return None

    # ====================== NEW: CONSOLE HISTORY ======================
    def _print_latest_entries(self):
        """Print the latest 10 entries (newest first) in a clean console table."""
        rows = []
        source = self.CSV_FILENAME

        # Try main CSV first
        if os.path.isfile(self.CSV_FILENAME):
            try:
                with open(self.CSV_FILENAME, "r", newline="", encoding="utf-8") as f:
                    rows = list(csv.DictReader(f))
            except Exception:
                pass

        # Fallback to backup.txt if CSV is empty/missing
        if not rows:
            rows = self._parse_backup_txt()
            source = self.BACKUP_TXT

        if not rows:
            print("📋 No history yet to display.")
            return

        latest = rows[-10:]          # last 10 (or fewer)
        latest.reverse()             # newest on top

        print("\n" + "═" * 80)
        print("📋 LATEST 10 ENTRIES (newest first)")
        print("-" * 80)
        print(f"{'#':<3} {'Timestamp':<20} {'ETH':<12} {'WETH':<12} {'cbBTC':<12} {'BTC-Equivalent':<12}")
        print("-" * 80)

        for i, row in enumerate(latest, 1):
            ts = row["timestamp_kst"][:19]  # clean timestamp
            eth = f"{float(row['eth_balance']):.6f}"
            weth = f"{float(row['weth_balance']):.6f}"
            cbbtc = f"{float(row['cbbtc_balance']):.6f}"
            btc_eq = row["btc-equivalent"]
            print(f"{i:<3} {ts:<20} {eth:<12} {weth:<12} {cbbtc:<12} {btc_eq:<12}")

        print("-" * 80)
        print(f"Showing {len(latest)} of {len(rows)} total entries • Source: {source}")
        print("═" * 80)

    # ====================== MAIN EXECUTION ======================
    def run(self):
        print("🔍 Base Wallet Recorder (Rolling 100-Entry .txt Backup + History View)\n")

        wallet_address = input("Enter your Base wallet address: ").strip()
        if not wallet_address:
            print("❌ No address provided.")
            return

        # Auto-restore if CSV missing/empty
        if not os.path.isfile(self.CSV_FILENAME) or os.path.getsize(self.CSV_FILENAME) == 0:
            print("📂 Main CSV missing or empty — restoring latest 100 entries from backup.txt...")
            self._restore_from_backup()

        print("\n📡 Fetching balances from Base + prices from CoinGecko...")

        row = None
        is_backup = False

        try:
            # LIVE FETCH
            eth_balance: Decimal = self.balance_checker.get_eth_balance(wallet_address)
            weth_balance: Decimal = self.balance_checker.get_weth_balance(wallet_address)
            cbbtc_balance: Decimal = self.balance_checker.get_cbbtc_balance(wallet_address)

            prices = self.price_fetcher.get_all_prices()
            btc_price = prices.get("btc")
            eth_price = prices.get("eth")

            timestamp_kst = self.get_kst_now()
            btc_equiv_str = self._calculate_btc_equivalent(
                eth_balance, weth_balance, cbbtc_balance, btc_price, eth_price
            )

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

        except Exception as e:
            print(f"⚠️ Live fetch failed: {str(e)}")
            print("📂 Loading latest matching record from backup.txt...")

            backup_row = self._load_latest_from_backup(wallet_address)
            if backup_row:
                row = backup_row.copy()
                row["timestamp_kst"] = self.get_kst_now() + " (BACKUP)"
                is_backup = True
                print("✅ Successfully loaded from backup.txt!")
            else:
                print("❌ No matching backup data available for this wallet.")
                return

        # Append to main CSV
        file_exists = os.path.isfile(self.CSV_FILENAME)
        with open(self.CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            if not file_exists:
                writer.writeheader()
                print(f"📁 Created new file → {self.CSV_FILENAME}")
            writer.writerow(row)

        # Update .txt backup ONLY on live data
        if not is_backup:
            try:
                with open(self.CSV_FILENAME, "r", newline="", encoding="utf-8") as f:
                    all_rows = list(csv.DictReader(f))
                latest_rows = all_rows[-self.MAX_BACKUP_ENTRIES:]
                self._write_rolling_backup_txt(latest_rows)
            except Exception as e:
                print(f"⚠️ Could not update backup.txt: {e}")

        # === Pretty summary (original) ===
        print("\n" + "═" * 80)
        status = "✅ SUCCESSFULLY RECORDED" if not is_backup else "⚠️ RECORDED FROM BACKUP"
        print(f"{status} — {row['timestamp_kst']}")
        print(f"Wallet         : {wallet_address}")
        print(f"ETH            : {float(row['eth_balance']):,.8f} ETH")
        print(f"WETH           : {float(row['weth_balance']):,.8f} WETH")
        print(f"cbBTC          : {float(row['cbbtc_balance']):,.8f} cbBTC")
        print("-" * 80)
        print(f"BTC Price      : ${row['btc_price_usd']}")
        print(f"ETH Price      : ${row['eth_price_usd']}")
        print(f"BTC-Equivalent : {row['btc-equivalent']} BTC")
        if is_backup:
            print("⚠️ NOTE: This is last known data from backup.txt")
        print("═" * 80)

        # === NEW FEATURE: Latest 10 entries ===
        self._print_latest_entries()

        # Final file info
        print(f"💾 Main history : {self.CSV_FILENAME}")
        print(f"📋 Backup (txt) : {self.BACKUP_TXT} (latest 100 entries)")

    def close(self):
        if hasattr(self, "balance_checker") and self.balance_checker:
            self.balance_checker.close()


if __name__ == "__main__":
    recorder = WalletRecorder()
    try:
        recorder.run()
    finally:
        recorder.close()
