from web3 import Web3
from web3.exceptions import ContractLogicError

# ================= CONFIG =================
BASE_RPC = "https://mainnet.base.org"  # Use Alchemy/Infura for better speed/reliability
w3 = Web3(Web3.HTTPProvider(BASE_RPC))

if not w3.is_connected():
    raise Exception("Failed to connect to Base RPC. Check URL or use private endpoint.")

POSITION_MANAGER_ADDR = Web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
VOTER_ADDR = Web3.to_checksum_address("0x16613524e02ad97eDfeF371bC883F2F5d6C480A5")  # Voter – for reference

WALLET_LOWER = input("Enter your Base wallet address (0x...): ").strip().lower()
try:
    WALLET = Web3.to_checksum_address(WALLET_LOWER)
except ValueError:
    print("Invalid wallet address format.")
    exit(1)

print(f"\n=== Aerodrome SlipStream Positions (Unstaked + Staked) for {WALLET} ===\n")

# ── ABI for NonfungiblePositionManager ──
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

manager = w3.eth.contract(address=POSITION_MANAGER_ADDR, abi=MANAGER_ABI)

# ── ABI for CLGauge (SlipStream gauges) ──
GAUGE_ABI = [
    {"constant": True, "inputs": [{"name": "depositor", "type": "address"}], "name": "stakedValues", "outputs": [{"name": "", "type": "uint256[]"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "pool", "outputs": [{"name": "", "type": "address"}], "type": "function"},
]

# ── Slimmed-down ABI for SlipStream CLPool slot0 (Aerodrome omits feeProtocol → shorter return tuple)
POOL_ABI = [
    {"inputs": [], "name": "slot0", "outputs": [
        {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
        {"internalType": "int24", "name": "tick", "type": "int24"},
        # We stop here — ignores any extra fields/packing differences
    ], "stateMutability": "view", "type": "function"}
]

# ── 1. Check unstaked positions ──
print("Unstaked positions (direct ownership):")
try:
    unstaked_count = manager.functions.balanceOf(WALLET).call()
    print(f" → {unstaked_count}")
    if unstaked_count > 0:
        for i in range(unstaked_count):
            token_id = manager.functions.tokenOfOwnerByIndex(WALLET, i).call()
            pos = manager.functions.positions(token_id).call()
            print(f"   NFT {token_id}: Liquidity {pos[7]:,}, Range {pos[5]} → {pos[6]}, Fees owed {pos[10]}/{pos[11]}")
    else:
        print("   (expected if all positions are staked)")
except Exception as e:
    print(f"   Error: {e}")

# ── 2. Check staked positions ──
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
            pool_addr = gauge.functions.pool().call()  # Get the linked pool once per gauge

            if staked_ids:
                found_any = True
                print(f"\nGauge {gauge_addr[:8]}...{gauge_addr[-6:]} has {len(staked_ids)} staked position(s):")
                print(f"   Linked pool: {pool_addr}")

                # Prepare pool contract
                pool = w3.eth.contract(address=pool_addr, abi=POOL_ABI)

                current_tick = None
                current_price = None

                try:
                    # Try slim ABI call first
                    slot0 = pool.functions.slot0().call()
                    sqrt_price_x96 = slot0[0]
                    current_tick = slot0[1]
                    current_price = (1.0001 ** current_tick) if current_tick is not None else None
                    print("   → slot0() decoded successfully (slim ABI)")
                except Exception as abi_err:
                    print(f"   → ABI slot0() failed: {abi_err}")
                    # Fallback: raw call + manual decode of first two fields
                    try:
                        slot0_selector = Web3.keccak(text="slot0()")[:4].hex()
                        raw = w3.eth.call({"to": pool_addr, "data": slot0_selector})
                        if len(raw) >= 64:
                            sqrt_price_x96 = int.from_bytes(raw[0:32], "big")
                            # tick is signed int24 → use signed=True on the relevant bytes
                            tick_bytes = raw[32:64]
                            current_tick = int.from_bytes(tick_bytes, "big", signed=True)
                            current_price = (1.0001 ** current_tick) if current_tick is not None else None
                            print("   → Fallback raw decode succeeded")
                        else:
                            print("   → Raw slot0 return too short")
                    except Exception as raw_err:
                        print(f"   → Raw slot0 call failed: {raw_err}")
                        current_tick = None

                for token_id in staked_ids:
                    pos = manager.functions.positions(token_id).call()
                    token0_short = pos[2][:10] + "..."
                    token1_short = pos[3][:10] + "..."
                    tick_lower = pos[5]
                    tick_upper = pos[6]

                    print(f"\n   NFT {token_id}: {token0_short} ↔ {token1_short}")
                    print(f"      Liquidity: {pos[7]:,}")
                    print(f"      Range ticks: {tick_lower:,} → {tick_upper:,}")
                    print(f"      Uncollected fees: {pos[10]:,} / {pos[11]:,}")

                    # ── Price range analysis ──
                    if current_tick is not None:
                        center_tick = (tick_lower + tick_upper) // 2
                        lower_price = 1.0001 ** tick_lower
                        upper_price = 1.0001 ** tick_upper
                        center_price = 1.0001 ** center_tick

                        print("\n      === Current Pool Price vs Your Range ===")
                        print(f"         Current tick       : {current_tick:,}")
                        print(f"         Current price      : ≈ {current_price:,.8f} token1 per token0")
                        print(f"         Your range (price) : {lower_price:,.8f} → {upper_price:,.8f}")
                        print(f"         Center of range    : ≈ {center_price:,.8f} (tick {center_tick:,})")

                        if current_tick < tick_lower:
                            ticks_off = tick_lower - current_tick
                            ratio = current_price / lower_price if lower_price > 0 else float('inf')
                            print(f"         ⚠️ BELOW range by {ticks_off:,} ticks "
                                  f"({ratio:.2%} of lower bound)")
                        elif current_tick > tick_upper:
                            ticks_off = current_tick - tick_upper
                            ratio = upper_price / current_price if current_price > 0 else float('inf')
                            print(f"         ⚠️ ABOVE range by {ticks_off:,} ticks "
                                  f"({ratio:.2%} of upper bound)")
                        else:
                            print("         ✅ INSIDE range – actively earning fees")

                        distance_pct = ((current_price / center_price) - 1) * 100 if center_price != 0 else 0
                        print(f"         Distance from center: {distance_pct:+.2f}% (price space)")
                        print("         (~6930 ticks ≈ 100% price move)")
                    else:
                        print("      (price data unavailable — pool may have custom slot0 layout)")

                    print("      ---")

            else:
                print(f"   Gauge {gauge_addr[:8]}... → no staked positions found for you")

        except ContractLogicError as cle:
            print(f"   Gauge {gauge_str} → contract error (wrong ABI or not a gauge?): {cle}")
        except ValueError:
            print(f"   Invalid gauge address: {gauge_str}")
        except Exception as e:
            print(f"   Error querying gauge {gauge_str}: {e}")

    if not found_any:
        print("\nNo staked positions detected in provided gauges.")
else:
    print("Skipped gauge check.")
    print("To find gauges:")
    print("  • Aerodrome UI → My Positions → click → view contract/tx")
    print("  • Basescan → wallet → ERC-721 transfers → outgoing to gauge addresses")
    print("  • Voter contract can help enumerate if you know pools")
