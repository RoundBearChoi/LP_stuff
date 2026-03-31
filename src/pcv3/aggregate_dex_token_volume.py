import pandas as pd
import glob
import os
from collections import defaultdict

# ===================================================================
# CONFIGURATION SECTION
# ===================================================================
OUTPUT_CSV_FILENAME = "aggregated_dex_token_volume.csv"
MAPPING_FILE = "volume_tokens_whole_list_mar_31st.txt"

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# BLACKLIST: tokens you NEVER want in the final CSV
# Add any symbol exactly as it appears in your volume files
BLACKLIST_SYMBOLS = [
    "币安人生",
    "雷神"
    # ← Add more here, one per line, e.g. "SPAMTOKEN", "$TRASH"
]
# ===================================================================
# END OF CONFIGURATION
# ===================================================================

chain_map = {
    'solana': 'sol',
    'base': 'base',
    'bsc': 'bsc',
    'ethereum': 'ethereum'
}

# === LOAD COINGECKO MAPPING ===
print(f"🔄 Loading CoinGecko mapping from {MAPPING_FILE}...")
mapping_df = pd.read_csv(MAPPING_FILE)

# NORMALIZE SYMBOLS (case-insensitive matching for cbBTC vs CBBTC, JitoSOL, etc.)
mapping_df['symbol_norm'] = mapping_df['symbol'].astype(str).str.upper().str.strip()
print(f"   Loaded {len(mapping_df):,} token mappings.")

# Step 1: Find all highest_volume_gems_*.csv files
files = glob.glob("highest_volume_gems_*.csv")
print(f"✅ Found {len(files)} files to process:")
for f in files:
    print(f"   • {f}")

if not files:
    raise FileNotFoundError("No files starting with 'highest_volume_gems_' were found.")

# Step 2: Process each file
dataframes = []
tokens_by_chain = defaultdict(list)

for file_path in files:
    basename = os.path.basename(file_path)
    try:
        parts = basename.split('_')
        chain_full = parts[3]
        chain_short = chain_map.get(chain_full.lower(), chain_full.lower())
    except (IndexError, AttributeError):
        chain_short = "unknown"
        print(f"⚠️  Could not parse chain from {basename} — using 'unknown'")

    df = pd.read_csv(file_path)
    df['chain'] = chain_short
    df['source_file'] = basename

    # NORMALIZE SYMBOL IN VOLUME DATA TOO
    df['symbol_norm'] = df['symbol'].astype(str).str.upper().str.strip()

    dataframes.append(df)
    tokens_by_chain[chain_short] = df['symbol'].tolist()

    print(f"   Loaded {len(df):>4} tokens → chain='{chain_short}' ({basename})")

# Step 3: Aggregate all chains
aggregate_df = pd.concat(dataframes, ignore_index=True)

# Step 4: ENRICH WITH COINGECKO (case-insensitive merge)
print("🔄 Merging with CoinGecko data (case-insensitive)...")
aggregate_df = aggregate_df.merge(
    mapping_df[['symbol_norm', 'coingecko_symbol', 'coingecko_id']],
    on='symbol_norm',
    how='left'
)

# Clean up temporary column
aggregate_df = aggregate_df.drop(columns=['symbol_norm'])

# Step 5: APPLY BLACKLIST (new feature you requested)
print(f"🧹 Applying blacklist ({len(BLACKLIST_SYMBOLS)} tokens)...")
aggregate_df = aggregate_df[~aggregate_df['symbol'].isin(BLACKLIST_SYMBOLS)].reset_index(drop=True)
print(f"   → Removed {len(BLACKLIST_SYMBOLS)} blacklisted tokens (including 币安人生 & 雷神)")

# Optional: sort by 24h volume descending
if '24h vol' in aggregate_df.columns:
    aggregate_df = aggregate_df.sort_values(by='24h vol', ascending=False).reset_index(drop=True)

# Reorder columns so CoinGecko columns sit right next to symbol
desired_order = [
    'chain', 'symbol', 'coingecko_symbol', 'coingecko_id',
    '24h vol', 'liquidity', 'market cap', 'fdv', 'source_file'
]
existing_cols = [col for col in desired_order if col in aggregate_df.columns]
aggregate_df = aggregate_df[existing_cols]

# Save the final enriched & cleaned CSV
aggregate_df.to_csv(OUTPUT_CSV_FILENAME, index=False)

# ===================================================================
# Final summary
# ===================================================================
print("\n" + "="*80)
print("🎉 AGGREGATION COMPLETE WITH COINGECKO ENRICHMENT + BLACKLIST!")
print(f"   • Total rows in CSV : {len(aggregate_df):,}")
print(f"   • Blacklisted tokens: {BLACKLIST_SYMBOLS}")
print(f"   • Saved as          : {OUTPUT_CSV_FILENAME}")
print("\nTokens by chain:")
for chain, token_list in tokens_by_chain.items():
    print(f"   • {chain:8} → {len(token_list):>4} tokens (before blacklist)")

# Quick verification that the two tokens are gone
print("\n🔍 Blacklist verification — these tokens should NOT appear:")
check_tokens = ["币安人生", "雷神"]
print(aggregate_df[aggregate_df['symbol'].isin(check_tokens)][['chain', 'symbol', 'coingecko_symbol', 'coingecko_id']].to_string(index=False))
