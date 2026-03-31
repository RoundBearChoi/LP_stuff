import json
from collections import defaultdict
import pandas as pd

# ==================== CONFIG ====================
# Change these if your filenames are different
KUCOIN_FILE = "kucoin_top_volume.json"
MEXC_FILE = "mexc_top_volume.json"
OUTPUT_CSV = "aggregated_base_token_volume.csv"

# Optional: set to True if you want a console preview
SHOW_PREVIEW = True
# ===============================================

def load_json(filename: str):
    """Load a JSON file safely."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

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

# Save to CSV
df.to_csv(OUTPUT_CSV, index=False)

print(f"✅ Aggregation complete with exchange breakdown!")
print(f"   • Processed {len(kucoin_data):,} KuCoin pairs + {len(mexc_data):,} MEXC pairs")
print(f"   • Found {len(df):,} unique base assets")
print(f"   • Output saved to: {OUTPUT_CSV}")

if SHOW_PREVIEW:
    print("\n🔍 Top 15 base tokens (with exchange split):")
    preview_cols = ["base_asset", "total_24h_volume_usd", 
                    "kucoin_24h_volume_usd", "mexc_24h_volume_usd",
                    "kucoin_quote_assets", "mexc_quote_assets"]
    print(df.head(15)[preview_cols].to_string(index=False))
