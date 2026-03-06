from web3 import Web3
from web3.exceptions import ContractLogicError

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
    ]

    POOL_ABI = [
        {"inputs": [], "name": "slot0", "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24", "name": "tick", "type": "int24"},
        ], "stateMutability": "view", "type": "function"}
    ]

    # ── Known tokens on Base (this permanently fixes cbBTC decimals) ──
    KNOWN_TOKENS = {
        "0x4200000000000000000000000000000000000006".lower(): ("WETH", 18),
        "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf".lower(): ("cbBTC", 8),
    }

    def __init__(self, rpc_url=None):
        rpc = rpc_url or self.BASE_RPC
        self.w3 = Web3(Web3.HTTPProvider(rpc))
        
        if not self.w3.is_connected():
            raise Exception("Failed to connect to Base RPC. Check URL or use private endpoint.")

        self.manager = self.w3.eth.contract(
            address=self.POSITION_MANAGER_ADDR, 
            abi=self.MANAGER_ABI
        )

    @staticmethod
    def tick_to_price(tick):
        try:
            return 1.0001 ** tick
        except (OverflowError, ValueError):
            return 0.0

    def run(self):
        """Main entry point - identical interactive flow as the original script"""
        WALLET_LOWER = input("Enter your Base wallet address (0x...): ").strip().lower()
        try:
            WALLET = Web3.to_checksum_address(WALLET_LOWER)
        except ValueError:
            print("Invalid wallet address format.")
            return

        print(f"\n=== Aerodrome SlipStream Positions (Unstaked + Staked) for {WALLET} ===\n")

        self._check_unstaked_positions(WALLET)
        self._check_staked_positions(WALLET)

    def _check_unstaked_positions(self, wallet):
        print("Unstaked positions (direct ownership):")
        try:
            unstaked_count = self.manager.functions.balanceOf(wallet).call()
            print(f" → {unstaked_count} positions")
            if unstaked_count > 0:
                for i in range(unstaked_count):
                    token_id = self.manager.functions.tokenOfOwnerByIndex(wallet, i).call()
                    pos = self.manager.functions.positions(token_id).call()
                    print(f"   NFT {token_id}: Liquidity {pos[7]:,}, Range {pos[5]:,} → {pos[6]}, Fees {pos[10]:,}/{pos[11]:,}")
            else:
                print("   (none found — all may be staked)")
        except Exception as e:
            print(f"   Error fetching unstaked: {e}")

    def _check_staked_positions(self, wallet):
        print("\nStaked positions (in gauges):")
        print("Paste gauge address(es) from Aerodrome UI / Basescan (comma-separated, or press Enter to skip):")
        gauge_input = input("> ").strip()

        if gauge_input:
            self._process_gauges(wallet, gauge_input)
        else:
            print("Gauge check skipped.")
            print("Tip: find gauges via")
            print("  • Aerodrome app → My Positions → view contract")
            print("  • Basescan wallet → ERC-721 transfers to gauge addresses")

    def _process_gauges(self, wallet, gauge_input):
        gauges = [g.strip() for g in gauge_input.split(',')]
        found_any = False

        for gauge_str in gauges:
            try:
                if self._process_single_gauge(wallet, gauge_str):
                    found_any = True
            except ContractLogicError as cle:
                print(f"   Gauge {gauge_str} → likely not a gauge or ABI mismatch: {cle}")
            except ValueError:
                print(f"   Invalid gauge address: {gauge_str}")
            except Exception as e:
                print(f"   Error with gauge {gauge_str}: {e}")

        if not found_any:
            print("\nNo staked positions found in the provided gauges.")

    def _process_single_gauge(self, wallet, gauge_str):
        gauge_addr = Web3.to_checksum_address(gauge_str)
        gauge = self.w3.eth.contract(address=gauge_addr, abi=self.GAUGE_ABI)

        staked_ids = gauge.functions.stakedValues(wallet).call()
        pool_addr = gauge.functions.pool().call()

        if not staked_ids:
            print(f"   Gauge {gauge_addr[:8]}... → no staked positions for this wallet")
            return False

        # Found staked positions
        print(f"\nGauge {gauge_addr[:8]}...{gauge_addr[-6:]} — {len(staked_ids)} staked position(s)")
        print(f"   Linked pool: {pool_addr}")

        # ── Get current tick ──
        current_tick = self._get_current_tick(pool_addr)

        # ── Show each position ──
        for token_id in staked_ids:
            self._print_position_details(token_id, current_tick)

        return True

    def _get_current_tick(self, pool_addr):
        pool = self.w3.eth.contract(address=pool_addr, abi=self.POOL_ABI)
        try:
            slot0 = pool.functions.slot0().call()
            print("   → slot0 decoded (slim ABI)")
            return slot0[1]
        except Exception:
            try:
                slot0_selector = Web3.keccak(text="slot0()")[:4].hex()
                raw = self.w3.eth.call({"to": pool_addr, "data": slot0_selector})
                if len(raw) >= 64:
                    tick = int.from_bytes(raw[32:64], "big", signed=True)
                    print("   → fallback raw decode OK")
                    return tick
            except Exception as e:
                print(f"   → could not get current tick: {e}")
        return None

    def _print_position_details(self, token_id, current_tick):
        pos = self.manager.functions.positions(token_id).call()
        t0_addr = pos[2]
        t1_addr = pos[3]
        tick_lower = pos[5]
        tick_upper = pos[6]
        liquidity = pos[7]
        fees0 = pos[10]
        fees1 = pos[11]

        sym0, dec0 = self._get_token_info(t0_addr)
        sym1, dec1 = self._get_token_info(t1_addr)

        print(f"\n   NFT {token_id}: {sym0} ↔ {sym1}")
        print(f"      Liquidity: {liquidity:,}")
        print(f"      Range ticks: {tick_lower:,} → {tick_upper:,}")
        print(f"      Uncollected fees: {fees0:,} / {fees1:,}")

        if current_tick is not None:
            self._print_price_analysis(sym0, sym1, dec0, dec1, tick_lower, tick_upper, current_tick)

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

        print("\n      === Price vs Range ===")
        print(f"         Current:   1 {sym0} = {p_current:.8g} {sym1}")
        print(f"         Range:     1 {sym0} = {p_lower:.8g} → {p_upper:.8g} {sym1}")
        print(f"         Center:    1 {sym0} = {p_center:.8g} {sym1} (tick {(tick_lower + tick_upper)//2:,})")

        if current_tick < tick_lower:
            print(f"         ⚠️ BELOW range by {tick_lower - current_tick:,} ticks")
        elif current_tick > tick_upper:
            print(f"         ⚠️ ABOVE range by {current_tick - tick_upper:,} ticks")
        else:
            print("         ✅ INSIDE range – earning fees")

        if p_center > 0:
            distance_pct = ((p_current / p_center) - 1) * 100
            print(f"         Price distance from center: {distance_pct:+.2f}%")
        print("      ---")


if __name__ == "__main__":
    checker = AerodromePositionChecker()
    checker.run()
