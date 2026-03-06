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

# ── ABI for Position Manager ──
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

# ── ABI snippet for Gauge (CLGauge for SlipStream) ──
GAUGE_ABI = [
    {"constant": True, "inputs": [{"name": "depositor", "type": "address"}], "name": "stakedValues", "outputs": [{"name": "", "type": "uint256[]"}], "type": "function"}
    # If your gauge uses different name (rare), try adding:
    # {"constant": True, "inputs": [{"name": "account", "type": "address"}], "name": "balanceOfNFT", "outputs": [{"name": "", "type": "uint256"}], "type": "function"},
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
            if staked_ids:
                found_any = True
                print(f"\nGauge {gauge_addr[:8]}...{gauge_addr[-6:]} has {len(staked_ids)} staked position(s):")
                for token_id in staked_ids:
                    pos = manager.functions.positions(token_id).call()
                    token0, token1 = pos[2][:10] + "...", pos[3][:10] + "..."
                    print(f"   NFT {token_id}: {token0} ↔ {token1}")
                    print(f"      Liquidity: {pos[7]:,}")
                    print(f"      Range ticks: {pos[5]} → {pos[6]}")
                    print(f"      Uncollected fees: {pos[10]:,} / {pos[11]:,}")
                    print("      ---")
            else:
                print(f"   Gauge {gauge_addr[:8]}... → no staked positions found for you")
        except ContractLogicError:
            print(f"   Gauge {gauge_str} → function 'stakedValues' not found or reverted (wrong ABI/gauge type?)")
        except ValueError:
            print(f"   Invalid gauge address: {gauge_str}")
        except Exception as e:
            print(f"   Error querying gauge {gauge_str}: {e}")
    
    if not found_any:
        print("\nNo staked positions detected in provided gauges.")
else:
    print("Skipped. To find gauges:")
    print("  • Aerodrome UI → My Positions → click position → view tx / contract details")
    print("  • Basescan → your wallet → ERC-721 transfers → look for outgoing to gauge-like addresses")
    print("  • Common Voter: 0x16613524e02ad97eDfeF371bC883F2F5d6C480A5 (can list gauges if you have pool addr)")

print("\nTips & Next Steps:")
print("- For pending AERO rewards: add `earned(address)` function to GAUGE_ABI and call it.")
print("- Want symbols? Add IERC20 minimal ABI and call `symbol()` on token0/token1.")
print("- Full automation hard without subgraph or known pool list.")
print("- UI (aerodrome.finance) or DeBank/Zapper still easiest for complete view.")
