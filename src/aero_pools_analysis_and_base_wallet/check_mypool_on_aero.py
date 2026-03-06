from web3 import Web3

# ────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────

# Use a reliable RPC – public one often fails silently
# Sign up free at https://www.alchemy.com → Base Mainnet → copy HTTPS URL
# Example: "https://base-mainnet.g.alchemy.com/v2/YOUR_API_KEY"
RPC_URL = "https://mainnet.base.org"  # ← CHANGE THIS for better results!

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Confirmed Aerodrome LP Sugar v3 contract (checksummed)
SUGAR_ADDRESS = Web3.to_checksum_address("0x68c19e13618c41158fe4baba1b8fb3a9c74bdb0a")

# Expanded ABI – covers classic (v2) unstaked/staked + concentrated (Slipstream)
SUGAR_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "_limit", "type": "uint256"},
            {"internalType": "uint256", "name": "_offset", "type": "uint256"},
            {"internalType": "address", "name": "_account", "type": "address"}
        ],
        "name": "positions",
        "outputs": [
            {
                "components": [
                    {"internalType": "uint256", "name": "id", "type": "uint256"},                # 0 = classic, >0 = NFT ID
                    {"internalType": "address", "name": "lp", "type": "address"},                # Pool address
                    {"internalType": "uint256", "name": "liquidity", "type": "uint256"},         # Total liquidity / deposited LP
                    {"internalType": "uint256", "name": "staked", "type": "uint256"},            # Staked in gauge
                    {"internalType": "uint256", "name": "amount0", "type": "uint256"},           # Unstaked token0
                    {"internalType": "uint256", "name": "amount1", "type": "uint256"},           # Unstaked token1
                    {"internalType": "uint256", "name": "staked0", "type": "uint256"},           # Staked token0
                    {"internalType": "uint256", "name": "staked1", "type": "uint256"},           # Staked token1
                    {"internalType": "int24", "name": "tick_lower", "type": "int24"},
                    {"internalType": "int24", "name": "tick_upper", "type": "int24"},
                    # You can add more fields like earned rewards, fees, etc. from Basescan ABI
                ],
                "internalType": "struct LpSugar.Position[]",
                "name": "",
                "type": "tuple[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

contract = w3.eth.contract(address=SUGAR_ADDRESS, abi=SUGAR_ABI)

# Slipstream NFT Manager (for concentrated positions fallback)
NFT_MANAGER_ADDRESS = Web3.to_checksum_address("0x827922686190790b37229fd06084350e74485b72")
NFT_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]
nft_contract = w3.eth.contract(address=NFT_MANAGER_ADDRESS, abi=NFT_ABI)


def check_aerodrome_lp_positions(raw_address: str):
    raw_address = raw_address.strip()
    if not raw_address:
        print("No address entered.")
        return False, []

    if not raw_address.startswith("0x"):
        raw_address = "0x" + raw_address

    try:
        user_address = Web3.to_checksum_address(raw_address)
    except ValueError:
        print("Invalid address format. Must be a valid Ethereum/Base address (0x + 40 hex chars).")
        return False, []

    print(f"→ Checking: {user_address}")
    print(f"→ Using RPC: {RPC_URL}")
    print("Querying LP Sugar v3...")

    LIMIT = 100
    OFFSET = 0
    all_active = []

    while True:
        try:
            raw_positions = contract.functions.positions(LIMIT, OFFSET, user_address).call()
        except Exception as e:
            print(f"Error calling positions(): {e}")
            print("Try switching to Alchemy/Infura RPC – public endpoint may be rate-limited.")
            break

        if not raw_positions:
            break

        for pos in raw_positions:
            try:
                pos_id, pool, liquidity, staked, amt0, amt1, staked0, staked1, tick_lower, tick_upper = pos[:10]
            except ValueError:
                print("ABI unpacking error – struct fields may have changed. Check Basescan ABI.")
                continue

            is_active = (liquidity > 0) or (staked > 0) or (amt0 > 0) or (amt1 > 0) or (staked0 > 0) or (staked1 > 0)

            if is_active:
                is_concentrated = (pos_id > 0) or (tick_lower != tick_upper)
                position_type = "Concentrated (Slipstream)" if is_concentrated else "Classic (v2-style)"
                status = "Staked in gauge" if staked > 0 else "Unstaked / Deposited"

                all_active.append({
                    "id": pos_id,
                    "pool": pool,
                    "liquidity": liquidity,
                    "staked": staked,
                    "unstaked_0": amt0,
                    "unstaked_1": amt1,
                    "staked_0": staked0,
                    "staked_1": staked1,
                    "ticks": f"{tick_lower} → {tick_upper}" if is_concentrated else "Full range",
                    "type": position_type,
                    "status": status
                })

        OFFSET += LIMIT

    # Fallback: Check NFT ownership for concentrated positions
    try:
        nft_balance = nft_contract.functions.balanceOf(user_address).call()
        if nft_balance > 0:
            print(f"→ You own {nft_balance} Slipstream NFT position(s) (concentrated liquidity).")
            if nft_balance > 0 and not any(p["type"] == "Concentrated (Slipstream)" for p in all_active):
                print("  → Sugar didn't list them – possible legacy/unstaked concentrated positions.")
    except Exception as e:
        print(f"Could not check NFT balance: {e}")

    has_positions = len(all_active) > 0

    print(f"\nResults for {user_address}:")
    if has_positions:
        print(f"Found {len(all_active)} active position(s):")
        for idx, p in enumerate(all_active, 1):
            print(f"  Position #{idx}:")
            print(f"    • Pool:            {p['pool']}")
            print(f"    • Type:            {p['type']}")
            print(f"    • Status:          {p['status']}")
            print(f"    • Liquidity:       {p['liquidity']:,}")
            print(f"    • Staked LP:       {p['staked']:,}")
            print(f"    • Staked tokens:   {p['staked_0']:,} / {p['staked_1']:,}")
            print(f"    • Unstaked tokens: {p['unstaked_0']:,} / {p['unstaked_1']:,}")
            print(f"    • Range:           {p['ticks']}")
            print(f"    • Position ID:     {p['id']}")
            print("    ────────────────────────────────────────")
    else:
        print("  No active positions detected via Sugar v3.")
        print("  Possible reasons:")
        print("    - Only unstaked classic LP tokens (not deposited/staked)")
        print("    - Positions too small (dust)")
        print("    - RPC returned empty (try Alchemy RPC)")
        print("    - Concentrated position not aggregated (check NFT balance above)")

    return has_positions, all_active


if __name__ == "__main__":
    print("=== Aerodrome LP Positions Checker (Staked + Unstaked) ===")
    print("Supports classic (v2) unstaked/staked + Slipstream concentrated.")
    print("Tip: Use Alchemy RPC for reliable results!\n")

    while True:
        addr_input = input("Enter Base address (0x...): ").strip()
        if not addr_input:
            print("No input – exiting.")
            break

        has_any, _ = check_aerodrome_lp_positions(addr_input)

        print("\nHas positions on Aerodrome? →", "YES" if has_any else "NO")
        print("=" * 70)

        again = input("Check another? (y/n): ").strip().lower()
        if again != 'y':
            print("Done.")
            break
