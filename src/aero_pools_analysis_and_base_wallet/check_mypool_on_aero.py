from web3 import Web3
import time
import os
from datetime import datetime

class AerodromePositionChecker:
    # ================= CONFIG =================
    BASE_RPC = "https://mainnet.base.org"
    POSITION_MANAGER_ADDR = Web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")

    # ── ABIs ──
    MANAGER_ABI = [
        {"constant": True, "inputs": [{"name": "owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "owner", "type": "address"}, {"name": "index", "type": "uint256"}], "name": "tokenOfOwnerByIndex", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "tokenId", "type": "uint256"}], "name": "positions", "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "tickSpacing", "type": "int24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"}
        ], "type": "function"}
    ]

    ERC20_ABI = [
        {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"}
    ]

    GAUGE_ABI = [
        {"constant": True, "inputs": [{"name": "depositor", "type": "address"}], "name": "stakedValues", "outputs": [{"name": "", "type": "uint256[]"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "pool", "outputs": [{"name": "", "type": "address"}], "type": "function"},
        {"constant": True, "inputs": [{"name": "account", "type": "address"}, {"name": "tokenId", "type": "uint256"}], "name": "earned", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
    ]

    POOL_ABI = [
        {"inputs": [], "name": "slot0", "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
        ], "stateMutability": "view", "type": "function"}
    ]

    # ── Known tokens ──
    KNOWN_TOKENS = {
        "0x4200000000000000000000000000000000000006".lower(): ("WETH", 18),
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf".lower(): ("cbBTC", 8),
        "0x940181a94a35a4569e4529a3cdfb74e38fd98631".lower(): ("AERO", 18),
    }

    # 🌱 ANSI Terminal Colors
    GREEN = "\033[92m"
    RED   = "\033[91m"
    RESET = "\033[0m"

    def __init__(self, rpc_url=None):
        rpc = rpc_url or self.BASE_RPC
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        if not self.w3.is_connected():
            raise Exception("Failed to connect to Base RPC.")
        self.manager = self.w3.eth.contract(address=self.POSITION_MANAGER_ADDR, abi=self.MANAGER_ABI)

    @staticmethod
    def tick_to_price(tick):
        try:
            return 1.0001 ** tick
        except (OverflowError, ValueError):
            return 0.0

    def _call_with_retry(self, func, max_retries=6, base_delay=3):
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                err = str(e).lower()
                if any(kw in err for kw in ["429", "rate limit", "too many requests", "limit exceeded", "timeout", "connection"]):
                    delay = base_delay * (2 ** attempt)
                    print(f"  ⚠️  RPC rate limit detected. Waiting {delay}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(delay)
                else:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(base_delay)
        return 0

    def run(self):
        WALLET_LOWER = input("Enter your Base wallet address (0x...): ").strip().lower()
        try:
            WALLET = Web3.to_checksum_address(WALLET_LOWER)
            self.wallet = WALLET
        except ValueError:
            print("Invalid wallet address format.")
            return

        print(f"\n=== Aerodrome SlipStream LIVE MONITOR for {WALLET} ===\n")

        self._check_unstaked_positions(WALLET)

        print("\nStaked positions (in gauges):")
        gauge_input = input("Paste gauge address(es) (comma-separated, or Enter to skip): ").strip()

        staked_positions = []
        if gauge_input:
            staked_positions = self._get_all_staked_positions(WALLET, gauge_input)

        if not staked_positions:
            print("No staked positions found.")
            return

        print(f"\n✅ Found {len(staked_positions)} staked position(s). Starting LIVE monitor...")
        print("   Price vs Range + Fees + Emissions updates every 60 seconds • Ctrl+C to stop\n")
        time.sleep(2)

        try:
            while True:
                self._live_update(staked_positions)
                self._countdown(60)
        except KeyboardInterrupt:
            print("\n\n👋 Monitor stopped. Goodbye!")

    def _check_unstaked_positions(self, wallet):
        print("Unstaked positions (direct ownership):")
        try:
            count = self._call_with_retry(lambda: self.manager.functions.balanceOf(wallet).call())
            print(f" → {count} positions")
            if count > 0:
                for i in range(count):
                    token_id = self._call_with_retry(lambda: self.manager.functions.tokenOfOwnerByIndex(wallet, i).call())
                    pos = self._call_with_retry(lambda: self.manager.functions.positions(token_id).call())
                    sym0, dec0 = self._get_token_info(pos[2])
                    sym1, dec1 = self._get_token_info(pos[3])
                    f0 = pos[10] / (10 ** dec0)
                    f1 = pos[11] / (10 ** dec1)
                    print(f"   NFT {token_id}: Liquidity {pos[7]:,}, Range {pos[5]:,} → {pos[6]}, Fees {f0:.6f} {sym0} / {f1:.6f} {sym1}")
            else:
                print("   (none found — all may be staked)")
        except Exception as e:
            print(f"   Error fetching unstaked: {e}")

    def _get_all_staked_positions(self, wallet, gauge_input):
        gauges = [g.strip() for g in gauge_input.split(',')]
        all_staked = []
        for gauge_str in gauges:
            try:
                gauge_addr = Web3.to_checksum_address(gauge_str)
                gauge = self.w3.eth.contract(address=gauge_addr, abi=self.GAUGE_ABI)

                staked_ids = self._call_with_retry(lambda: gauge.functions.stakedValues(wallet).call())
                pool_addr = self._call_with_retry(lambda: gauge.functions.pool().call())

                if staked_ids:
                    print(f"\nGauge {gauge_addr[:8]}...{gauge_addr[-6:]} — {len(staked_ids)} staked position(s)")
                    print(f"   Linked pool: {pool_addr}")
                    for token_id in staked_ids:
                        pos = self._call_with_retry(lambda: self.manager.functions.positions(token_id).call())
                        pending = self._call_with_retry(lambda: gauge.functions.earned(wallet, token_id).call())
                        all_staked.append({
                            "token_id": token_id,
                            "pool_addr": pool_addr,
                            "pos": pos,
                            "gauge": gauge_addr,
                            "pending_emissions": pending
                        })
            except Exception as e:
                print(f"   Error with gauge {gauge_str}: {e}")
        return all_staked

    def _live_update(self, staked_positions):
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"=== Aerodrome SlipStream LIVE MONITOR — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        print(f"Monitoring {len(staked_positions)} staked position(s) • Refresh every 60s\n")

        for pos_data in staked_positions:
            token_id = pos_data["token_id"]
            pool_addr = pos_data["pool_addr"]
            pos = pos_data["pos"]
            pending = pos_data.get("pending_emissions", 0)
            current_tick = self._get_current_tick(pool_addr)
            self._print_live_position(token_id, pos, current_tick, pending)

        print("\n" + "="*80)

    def _countdown(self, seconds):
        for remaining in range(seconds, 0, -1):
            print(f"\rNext refresh in {remaining:2d} seconds... (Ctrl+C to stop)", end="", flush=True)
            time.sleep(1)
        print("\r" + " " * 70)

    def _get_current_tick(self, pool_addr):
        pool = self.w3.eth.contract(address=pool_addr, abi=self.POOL_ABI)
        def fetch():
            try:
                slot0 = pool.functions.slot0().call()
                return slot0[1]
            except:
                selector = Web3.keccak(text="slot0()")[:4].hex()
                raw = self.w3.eth.call({"to": pool_addr, "data": selector})
                if len(raw) >= 64:
                    return int.from_bytes(raw[32:64], "big", signed=True)
                raise
        return self._call_with_retry(fetch)

    def _print_live_position(self, token_id, pos, current_tick, pending_emissions):
        t0_addr = pos[2]
        t1_addr = pos[3]
        tick_lower = pos[5]
        tick_upper = pos[6]
        liquidity = pos[7]
        fees0 = pos[10]
        fees1 = pos[11]

        sym0, dec0 = self._get_token_info(t0_addr)
        sym1, dec1 = self._get_token_info(t1_addr)

        f0 = fees0 / (10 ** dec0)
        f1 = fees1 / (10 ** dec1)

        print(f"\n   NFT {token_id}: {sym0} ↔ {sym1}")
        print(f"      Liquidity: {liquidity:,}")
        print(f"      Range ticks: {tick_lower:,} → {tick_upper:,}")
        print(f"      Uncollected fees: {f0:.6f} {sym0} / {f1:.6f} {sym1}")

        # 🌱 Emissions display
        if pending_emissions > 0:
            aero_formatted = pending_emissions / 1e18
            print(f"      🌱 Pending emissions: {aero_formatted:,.4f} AERO")
        else:
            print("      🌱 Pending emissions: 0 AERO")

        if current_tick is not None:
            self._print_price_analysis(sym0, sym1, dec0, dec1, tick_lower, tick_upper, current_tick)
        else:
            print("      ⚠️  Could not fetch current price (RPC issue)")

    def _get_token_info(self, token_addr):
        lower = token_addr.lower()
        if lower in self.KNOWN_TOKENS:
            return self.KNOWN_TOKENS[lower]
        try:
            c = self.w3.eth.contract(token_addr, abi=self.ERC20_ABI)
            sym = c.functions.symbol().call()
            dec = c.functions.decimals().call()
            return sym, dec
        except:
            return token_addr[:8] + "...", 18

    def _print_price_analysis(self, sym0, sym1, dec0, dec1, tick_lower, tick_upper, current_tick):
        p_raw = self.tick_to_price(current_tick)
        p_lower_raw = self.tick_to_price(tick_lower)
        p_upper_raw = self.tick_to_price(tick_upper)
        center_raw = self.tick_to_price((tick_lower + tick_upper) // 2)

        adjust = 10 ** (dec0 - dec1)
        p_current = p_raw * adjust
        p_lower   = p_lower_raw * adjust
        p_upper   = p_upper_raw * adjust
        p_center  = center_raw * adjust

        print("\n      === Price vs Range (LIVE) ===")
        print(f"         Current:   1 {sym0} = {p_current:.8g} {sym1}")
        print(f"         Range:     1 {sym0} = {p_lower:.8g} → {p_upper:.8g} {sym1}")
        print(f"         Center:    1 {sym0} = {p_center:.8g} {sym1} (tick {(tick_lower + tick_upper)//2:,})")

        # COLORED STATUS
        if current_tick < tick_lower:
            diff = tick_lower - current_tick
            print(f"         {self.RED}↓ BELOW range by {diff:,} ticks{self.RESET}")
        elif current_tick > tick_upper:
            diff = current_tick - tick_upper
            print(f"         {self.RED}↑ ABOVE range by {diff:,} ticks{self.RESET}")
        else:
            print(f"         {self.GREEN}INSIDE range{self.RESET}")

        # NEW: Edge usage % (100% = at edge / out of range)
        if p_center > 0:
            dev = (p_current / p_center) - 1
            if dev >= 0:
                # drifting toward upper
                half = (p_upper / p_center) - 1
                progress = (dev / half * 100) if half > 0 else 0
                arrow = "↑"
                edge = "upper"
            else:
                # drifting toward lower
                half = 1 - (p_lower / p_center)
                progress = ((-dev) / half * 100) if half > 0 else 0
                arrow = "↓"
                edge = "lower"

            extra = " (out of range)" if progress >= 100 else ""
            print(f"         Edge usage: {arrow} {progress:.2f}% toward {edge} edge{extra}")
        print("      ---")

if __name__ == "__main__":
    checker = AerodromePositionChecker()
    checker.run()
