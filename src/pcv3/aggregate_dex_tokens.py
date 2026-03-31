import pandas as pd
import glob
import os
from collections import defaultdict
from pathlib import Path

# ===================================================================
# Python script to aggregate highest_volume_gems_* CSV files
# ===================================================================
# What this does:
#   1. Dynamically discovers ALL files matching "highest_volume_gems_*.csv"
#   2. Parses the chain name from the filename (e.g. solana, base, bsc, ethereum)
#   3. Creates a dictionary (array-like) with short chain keys you requested:
#        tokens_by_chain = {
#            'sol': [...list of symbols...],
#            'base': [...],
#            'bsc': [...],
#            'ethereum': [...]
#        }
#   4. Adds a 'chain' column to every row (CRITICAL — symbols like USDC, USDT, WETH appear on multiple chains)
#   5. Keeps 100% of the original data (24h vol, liquidity, market cap, fdv + new columns)
#   6. Saves everything to aggregate_highest_volume_dex_tokens.csv
#   7. Optional: sorts by 24h volume descending for easy analysis
#
# Edge cases handled:
#   - Duplicate symbols across chains (resolved by 'chain' column)
#   - Filenames with different numbers (e.g. _100, _42, _146, _103)
#   - Missing files or extra files in the folder
#   - Zero/NaN values preserved exactly as in source CSVs
#   - Very large files (pandas handles millions of rows easily)
#
# Nuances / implications:
#   - The term "gems" in the filenames is marketing — the data actually contains stables (USDC, USDT),
#     blue-chips (WETH, WBTC), and high-volume tokens. The aggregation treats everything equally.
#   - Market-cap/FDV = 0 on some rows is preserved — these are often new or wrapped tokens.
#   - You can later filter the CSV by chain, volume threshold, liquidity/MC ratio, etc.
# ===================================================================

# Step 1: Define your preferred short chain names (exactly as you requested)
chain_map = {
    'solana': 'sol',
    'base': 'base',
    'bsc': 'bsc',
    'ethereum': 'ethereum'
}

# Step 2: Find all matching files in the current directory
files = glob.glob("highest_volume_gems_*.csv")
print(f"✅ Found {len(files)} files to process:")
for f in files:
    print(f"   • {f}")

if not files:
    raise FileNotFoundError("No files starting with 'highest_volume_gems_' were found in the current folder.")

# Step 3: Process each file and build both the aggregated DataFrame and the per-chain token list
dataframes = []
tokens_by_chain = defaultdict(list)   # This is your "array of sol, base, bsc, ethereum"

for file_path in files:
    # Extract full chain name from filename (highest_volume_gems_SOLANA_100.csv → "solana")
    basename = os.path.basename(file_path)
    try:
        # Split: ['highest', 'volume', 'gems', 'solana', '100']
        parts = basename.split('_')
        chain_full = parts[3]   # guaranteed by the naming pattern you used
        chain_short = chain_map.get(chain_full.lower(), chain_full.lower())
    except (IndexError, AttributeError):
        chain_short = "unknown"
        print(f"⚠️  Could not parse chain from {basename} — using 'unknown'")

    # Load the CSV exactly as-is
    df = pd.read_csv(file_path)

    # Add traceability columns
    df['chain'] = chain_short
    df['source_file'] = basename

    # Store full rows for aggregation
    dataframes.append(df)

    # Store only the symbol list for your requested "array"
    tokens_by_chain[chain_short] = df['symbol'].tolist()

    print(f"   Loaded {len(df):>4} tokens → chain='{chain_short}' ({basename})")

# Step 4: Create the single aggregated DataFrame (all data preserved)
aggregate_df = pd.concat(dataframes, ignore_index=True)

# Optional but useful: sort by 24h volume (highest first) so the CSV opens ready for analysis
if '24h vol' in aggregate_df.columns:
    aggregate_df = aggregate_df.sort_values(by='24h vol', ascending=False).reset_index(drop=True)

# Reorder columns nicely (chain first, then original columns)
desired_order = ['chain', 'symbol', '24h vol', 'liquidity', 'market cap', 'fdv', 'source_file']
# Only keep columns that actually exist
existing_cols = [col for col in desired_order if col in aggregate_df.columns]
aggregate_df = aggregate_df[existing_cols]

# Step 5: Save the final aggregated CSV
output_filename = "aggregate_highest_volume_dex_tokens.csv"
aggregate_df.to_csv(output_filename, index=False)

# ===================================================================
# Final summary & usage tips
# ===================================================================
print("\n" + "="*80)
print("🎉 AGGREGATION COMPLETE!")
print(f"   • Total rows in CSV : {len(aggregate_df):,}")
print(f"   • Columns           : {list(aggregate_df.columns)}")
print(f"   • Saved as          : {output_filename}")
print("\nTokens by chain (your requested array):")
for chain, token_list in tokens_by_chain.items():
    print(f"   • {chain:8} → {len(token_list):>4} tokens (example: {token_list[:5]})")
