#!/usr/bin/env python3
"""
CoinGecko Exchange ID Filter - Two Stage
=======================================
First keeps exchanges matching INCLUDE_KEYWORDS, 
then removes any that match EXCLUDE_KEYWORDS.
"""

# =============================================================================
# ============================ CONFIG SECTION =================================
# =============================================================================

JSON_FILE = "coingecko_exchange_ids.json"          
OUTPUT_FILE = "filtered_exchanges.txt"             

# === STAGE 1: INCLUDE ===
# Keep ONLY exchanges that match ANY of these keywords
INCLUDE_KEYWORDS = [
    "uniswap",
    "pancake",
    "pump",
    "humidifi",
    "aero",
    "orca",
    "fluid",
    "raydium",
    "changenow",
    #"curve",
    #"hyperliquid",
    #"balancer",
]

# === STAGE 2: EXCLUDE ===
# From the results above, remove exchanges that match ANY of these keywords
EXCLUDE_KEYWORDS = [
    "arbitrum",
    "monad",
    "polygon",
    "avalanche",
    "optimism",
    "unichain",
    "celo",
    "fraxtal",
    "gnosis",
    "plasma",
    "plume",
    "sonic",
    "tac",
    "taico",
    "xdc",
    "fantom",
    "moonbeam",
    "linea",
    "aptos",
    "blast",
    "world-chain",
    "x-layer",
    "zora",
    "soneium",
    "eclipse",
    "abstract",
]

SHOW_PREVIEW = True                                
PREVIEW_COUNT = 10                                 

SAVE_TO_FILE = True                                
# =============================================================================
# ========================== END OF CONFIG ====================================
# =============================================================================

import json
from pathlib import Path


def load_exchanges(json_path: str) -> list[str]:
    """Load the CoinGecko exchange ID list."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(
            f"❌ File not found: {path}\n"
            f"   Please save the provided exchange list as '{json_path}' "
            f"in the same folder as this script."
        )
    
    with open(path, "r", encoding="utf-8") as f:
        exchanges: list[str] = json.load(f)
    
    print(f"✅ Loaded {len(exchanges):,} exchange IDs from {path}")
    return exchanges


def filter_exchanges(exchanges: list[str], 
                    include_keywords: list[str], 
                    exclude_keywords: list[str]) -> list[str]:
    """Two-stage filter:
    1. Keep only exchanges matching any INCLUDE keyword
    2. Then remove any that match any EXCLUDE keyword
    """
    include_lower = [kw.lower() for kw in include_keywords]
    exclude_lower = [kw.lower() for kw in exclude_keywords]
    
    # Stage 1: Keep matches from INCLUDE
    stage1 = [
        ex for ex in exchanges
        if any(kw in ex.lower() for kw in include_lower)
    ]
    
    print(f"📌 Stage 1 (INCLUDE): Kept {len(stage1):,} exchanges")
    
    # Stage 2: Remove matches from EXCLUDE
    filtered = [
        ex for ex in stage1
        if not any(kw in ex.lower() for kw in exclude_lower)
    ]
    
    filtered_sorted = sorted(filtered)
    print(f"📌 Stage 2 (EXCLUDE): Removed {len(stage1) - len(filtered):,} exchanges")
    print(f"   → Final result: {len(filtered_sorted):,} exchanges")
    
    return filtered_sorted


def print_preview(filtered: list[str], count: int):
    """Print a nice preview of the filtered list."""
    if not filtered:
        print("   (No matches found)")
        return
    
    print(f"\n📋 Preview (first {min(count, len(filtered))}):")
    for ex in filtered[:count]:
        print(f"   • {ex}")
    
    if len(filtered) > count:
        print(f"   ... and {len(filtered) - count:,} more")


def save_filtered(filtered: list[str], output_path: str):
    """Save the filtered list to a plain text file."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered))
    print(f"💾 Saved {len(filtered):,} exchanges to → {output_path}")


def main():
    # Load data
    exchanges = load_exchanges(JSON_FILE)
    
    # Perform two-stage filtering
    filtered = filter_exchanges(exchanges, INCLUDE_KEYWORDS, EXCLUDE_KEYWORDS)
    
    # Preview
    if SHOW_PREVIEW:
        print_preview(filtered, PREVIEW_COUNT)
    
    # Save
    if SAVE_TO_FILE and filtered:
        save_filtered(filtered, OUTPUT_FILE)
    
    # Final stats
    print(f"\n📊 Summary")
    print(f"   Original     : {len(exchanges):,}")
    print(f"   After filter : {len(filtered):,}")


if __name__ == "__main__":
    main()
