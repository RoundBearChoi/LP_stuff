from web3 import Web3
from web3.exceptions import ContractLogicError

# ================= CONFIG =================
BASE_RPC = "https://mainnet.base.org"  # Consider Alchemy/Infura for reliability
w3 = Web3(Web3.HTTPProvider(BASE_RPC))

if not w3.is_connected():
    raise Exception("Failed to connect to Base RPC. Check URL or use private endpoint.")

POSITION_MANAGER_ADDR = Web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")

WALLET_LOWER = input("Enter your Base wallet address (0x...): ").strip().lower()
try:
    WALLET = Web3.to_checksum_address(WALLET_LOWER)
except ValueError:
    print("Invalid wallet address format.")
    exit(1)

print(f"\n=== Aerodrome SlipStream Positions (Unstaked + Staked) for {WALLET} ===\n")

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

manager = w3.eth.contract(address=POSITION_MANAGER_ADDR, abi=MANAGER_ABI)

# ── Known tokens on Base (this permanently fixes cbBTC decimals) ──
KNOWN_TOKENS = {
    "0x4200000000000000000000000000000000000006".lower(): ("WETH", 18),
    "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf".lower(): ("cbBTC", 8),
    # Add more pairs here anytime (example):
    # "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913".lower(): ("USDC", 6),
}

# ── Helper: safe tick → raw price ──
def tick_to_price(tick):
    try:
        return 1.0001 ** tick
    except (OverflowError, ValueError):
        return 0.0

# ── 1. Unstaked positions ──
print("Unstaked positions (direct ownership):")
try:
    unstaked_count = manager.functions.balanceOf(WALLET).call()
    print(f" → {unstaked_count} positions")
    if unstaked_count > 0:
        for i in range(unstaked_count):
            token_id = manager.functions.tokenOfOwnerByIndex(WALLET, i).call()
            pos = manager.functions.positions(token_id).call()
            print(f"   NFT {token_id}: Liquidity {pos[7]:,}, Range {pos[5]:,} → {pos[6]}, Fees {pos[10]:,}/{pos[11]:,}")
    else:
        print("   (none found — all may be staked)")
except Exception as e:
    print(f"   Error fetching unstaked: {e}")

# ── 2. Staked positions ──
print("\nStaked positions (in gauges):")
print("Paste gauge address(es) from Aerodrome UI / Basescan (comma-separated, or press Enter to skip):")
gauge_input = input("> ").strip()

if gauge_input:
    gauges = [g.strip() for g in gauge_input.split(',')]
    found_any = False

    for gauge_str in gauges:
        try:
            gauge_addr = Web3.to_checksum_address(gauge_str)
            gauge = w3.eth.contract(address=gauge_addr, abi=GAUGE_ABI)

            staked_ids = gauge.functions.stakedValues(WALLET).call()
            pool_addr = gauge.functions.pool().call()

            if staked_ids:
                found_any = True
                print(f"\nGauge {gauge_addr[:8]}...{gauge_addr[-6:]} — {len(staked_ids)} staked position(s)")
                print(f"   Linked pool: {pool_addr}")

                # ── Get current tick ──
                pool = w3.eth.contract(address=pool_addr, abi=POOL_ABI)
                current_tick = None
                try:
                    slot0 = pool.functions.slot0().call()
                    current_tick = slot0[1]
                    print("   → slot0 decoded (slim ABI)")
                except Exception:
                    try:
                        slot0_selector = Web3.keccak(text="slot0()")[:4].hex()
                        raw = w3.eth.call({"to": pool_addr, "data": slot0_selector})
                        if len(raw) >= 64:
                            current_tick = int.from_bytes(raw[32:64], "big", signed=True)
                            print("   → fallback raw decode OK")
                    except Exception as e:
                        print(f"   → could not get current tick: {e}")

                # ── Show each position ──
                for token_id in staked_ids:
                    pos = manager.functions.positions(token_id).call()
                    t0_addr = pos[2]
                    t1_addr = pos[3]
                    tick_lower = pos[5]
                    tick_upper = pos[6]
                    liquidity = pos[7]
                    fees0 = pos[10]
                    fees1 = pos[11]

                    # === Robust symbol + decimals (known tokens fallback) ===
                    t0_lower = t0_addr.lower()
                    if t0_lower in KNOWN_TOKENS:
                        sym0, dec0 = KNOWN_TOKENS[t0_lower]
                    else:
                        try:
                            c = w3.eth.contract(t0_addr, abi=ERC20_ABI)
                            sym0 = c.functions.symbol().call()
                            dec0 = c.functions.decimals().call()
                        except:
                            sym0 = t0_addr[:8] + "..."
                            dec0 = 18

                    t1_lower = t1_addr.lower()
                    if t1_lower in KNOWN_TOKENS:
                        sym1, dec1 = KNOWN_TOKENS[t1_lower]
                    else:
                        try:
                            c = w3.eth.contract(t1_addr, abi=ERC20_ABI)
                            sym1 = c.functions.symbol().call()
                            dec1 = c.functions.decimals().call()
                        except:
                            sym1 = t1_addr[:8] + "..."
                            dec1 = 18

                    print(f"\n   NFT {token_id}: {sym0} ↔ {sym1}")
                    print(f"      Liquidity: {liquidity:,}")
                    print(f"      Range ticks: {tick_lower:,} → {tick_upper:,}")
                    print(f"      Uncollected fees: {fees0:,} / {fees1:,}")

                    if current_tick is not None:
                        p_raw = tick_to_price(current_tick)
                        p_lower_raw = tick_to_price(tick_lower)
                        p_upper_raw = tick_to_price(tick_upper)
                        center_raw = tick_to_price((tick_lower + tick_upper) // 2)

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

            else:
                print(f"   Gauge {gauge_addr[:8]}... → no staked positions for this wallet")

        except ContractLogicError as cle:
            print(f"   Gauge {gauge_str} → likely not a gauge or ABI mismatch: {cle}")
        except ValueError:
            print(f"   Invalid gauge address: {gauge_str}")
        except Exception as e:
            print(f"   Error with gauge {gauge_str}: {e}")

    if not found_any:
        print("\nNo staked positions found in the provided gauges.")
else:
    print("Gauge check skipped.")
    print("Tip: find gauges via")
    print("  • Aerodrome app → My Positions → view contract")
    print("  • Basescan wallet → ERC-721 transfers to gauge addresses")
