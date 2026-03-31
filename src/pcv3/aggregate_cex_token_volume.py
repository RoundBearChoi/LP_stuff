import json
from collections import defaultdict
import pandas as pd

# ==================== CONFIG ====================
# Change these if your filenames are different
KUCOIN_FILE = "kucoin_top_volume.json"
MEXC_FILE = "mexc_top_volume.json"
OUTPUT_CSV = "aggregated_cex_token_volume.csv"
MAPPING_FILE = "volume_tokens_whole_list_mar_31st.txt"   # ← your CoinGecko mapping file

# Optional: set to True if you want a console preview
SHOW_PREVIEW = True
# ===============================================

def load_json(filename: str):
    """Load a JSON file safely."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

# === LOAD COINGECKO MAPPING (NEW — added exactly as you requested) ===
print(f"🔄 Loading CoinGecko mapping from {MAPPING_FILE}...")
mapping_df = pd.read_csv(MAPPING_FILE)
print(f"   Loaded {len(mapping_df):,} token mappings (symbol → coingecko_symbol + coingecko_id).")

# Load both datasets
kucoin_data = load_json(KUCOIN_FILE)
mexc_data = load_json(MEXC_FILE)

# Separate tracking per exchange
vol_kucoin = defaultdict(float)
vol_mexc = defaultdict(float)
quotes_kucoin = defaultdict(set)
quotes_mexc = defaultdict(set)

# Process KuCoin data
for item in kucoin_data:
    base = str(item.get("base_asset", "")).strip().upper()
    quote = str(item.get("quote_asset", "")).strip().upper()
    volume_usd = float(item.get("quote_volume_usd", 0.0))
    
    if base:
        vol_kucoin[base] += volume_usd
        quotes_kucoin[base].add(quote)

# Process MEXC data
for item in mexc_data:
    base = str(item.get("base_asset", "")).strip().upper()
    quote = str(item.get("quote_asset", "")).strip().upper()
    volume_usd = float(item.get("quote_volume_usd", 0.0))
    
    if base:
        vol_mexc[base] += volume_usd
        quotes_mexc[base].add(quote)

# Combine all unique base assets
all_bases = sorted(set(vol_kucoin.keys()) | set(vol_mexc.keys()))

# Build rows
rows = []
for base in all_bases:
    vk = round(vol_kucoin[base], 2)
    vm = round(vol_mexc[base], 2)
    total = round(vk + vm, 2)
    
    qk = ", ".join(sorted(quotes_kucoin[base])) if quotes_kucoin[base] else ""
    qm = ", ".join(sorted(quotes_mexc[base])) if quotes_mexc[base] else ""
    
    rows.append({
        "base_asset": base,
        "total_24h_volume_usd": total,
        "kucoin_24h_volume_usd": vk,
        "mexc_24h_volume_usd": vm,
        "kucoin_quote_assets": qk,
        "mexc_quote_assets": qm,
        "kucoin_pairs": len(quotes_kucoin[base]),
        "mexc_pairs": len(quotes_mexc[base])
    })

df = pd.DataFrame(rows)

# Sort by total volume (most active base tokens first)
df = df.sort_values(by="total_24h_volume_usd", ascending=False).reset_index(drop=True)

# === ENRICH WITH COINGECKO COLUMNS (exactly as requested — added right next to base_asset) ===
print("🔄 Adding coingecko_symbol and coingecko_id columns...")
df = df.merge(
    mapping_df[['symbol', 'coingecko_symbol', 'coingecko_id']].rename(columns={'symbol': 'base_asset'}),
    on='base_asset',
    how='left'          # keeps EVERY row — unmatched symbols just get NaN
)

# Reorder columns so the two new CoinGecko columns sit immediately after base_asset
desired_order = [
    'base_asset', 'coingecko_symbol', 'coingecko_id',
    'total_24h_volume_usd', 'kucoin_24h_volume_usd', 'mexc_24h_volume_usd',
    'kucoin_quote_assets', 'mexc_quote_assets',
    'kucoin_pairs', 'mexc_pairs'
]
existing_cols = [col for col in desired_order if col in df.columns]
df = df[existing_cols]

# Save to CSV
df.to_csv(OUTPUT_CSV, index=False)

print(f"✅ Aggregation complete with CoinGecko enrichment!")
print(f"   • Processed {len(kucoin_data):,} KuCoin pairs + {len(mexc_data):,} MEXC pairs")
print(f"   • Found {len(df):,} unique base assets")
print(f"   • Output saved to: {OUTPUT_CSV}")

if SHOW_PREVIEW:
    print("\n🔍 Top 15 base tokens (with CoinGecko + exchange split):")
    preview_cols = ["base_asset", "coingecko_symbol", "coingecko_id",
                    "total_24h_volume_usd", "kucoin_24h_volume_usd", "mexc_24h_volume_usd"]
    print(df.head(15)[preview_cols].to_string(index=False))
