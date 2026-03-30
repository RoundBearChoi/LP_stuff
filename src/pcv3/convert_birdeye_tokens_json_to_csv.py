import json
import csv

# ====================== CONFIG ======================
input_file = "highest_volume_gems_solana.json"
output_file = "highest_volume_gems_solana.csv"   # exactly the name you asked for

# Column headers exactly as you specified
fieldnames = ["symbol", "24h vol", "liquidity", "market cap", "fdv"]
# ===================================================

try:
    # 1. Load the entire JSON (safe for typical gem-list sizes; see edge-case notes below)
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Write to CSV
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()                     # writes the exact headers you want

        row_count = 0
        for token in data:
            row = {
                "symbol": token.get("symbol", ""),
                "24h vol": token.get("volume_24h_usd", 0),
                "liquidity": token.get("liquidity", 0),
                "market cap": token.get("market_cap", 0),
                "fdv": token.get("fdv", 0),
            }
            writer.writerow(row)
            row_count += 1

    print(f"✅ Conversion complete!")
    print(f"   • Input  : {input_file} ({len(data):,} tokens)")
    print(f"   • Output : {output_file} ({row_count:,} rows written)")

except FileNotFoundError:
    print(f"❌ Error: Could not find '{input_file}'. Make sure the JSON is in the same folder as this script.")
except json.JSONDecodeError:
    print(f"❌ Error: '{input_file}' is not valid JSON.")
except Exception as e:
    print(f"❌ Unexpected error: {e}")

