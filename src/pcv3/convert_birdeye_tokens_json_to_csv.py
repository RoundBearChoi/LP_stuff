import json
import csv
import os
import glob

# ====================== CONFIG ======================
# Only change this if you ever want a different prefix
FILE_PREFIX = "highest_volume_gems_"

# Column headers (exactly as you originally wanted)
FIELDNAMES = ["symbol", "24h vol", "liquidity", "market cap", "fdv"]
# ===================================================

def convert_json_to_csv(json_path: str):
    """Convert a single Birdeye JSON to CSV."""
    try:
        # Derive output CSV name (e.g. "xxx.json" → "xxx.csv")
        csv_path = os.path.splitext(json_path)[0] + ".csv"

        # 1. Load JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. Write CSV
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

            row_count = 0
            for token in data:
                row = {
                    "symbol": token.get("symbol", ""),
                    "24h vol": token.get("volume_24h_usd", 0),
                    "liquidity": token.get("liquidity", 0),
                    "market cap": token.get("market_cap", 0) or token.get("mc", 0),
                    "fdv": token.get("fdv", 0),
                }
                writer.writerow(row)
                row_count += 1

        print(f"✅ Converted: {json_path} → {csv_path} ({row_count:,} tokens)")

    except FileNotFoundError:
        print(f"❌ Skipped (file not found): {json_path}")
    except json.JSONDecodeError:
        print(f"❌ Skipped (invalid JSON): {json_path}")
    except Exception as e:
        print(f"❌ Error processing {json_path}: {e}")


# ============== MAIN PROGRAM ==============
if __name__ == "__main__":
    print(f"🔍 Looking for all JSON files starting with '{FILE_PREFIX}'...\n")

    # Find every matching JSON in the current directory
    pattern = f"{FILE_PREFIX}*.json"
    json_files = glob.glob(pattern)

    if not json_files:
        print(f"❌ No files found matching '{pattern}' in the current folder.")
        print("   Make sure your highest_volume_gems_*.json files are here.")
        exit(1)

    print(f"📦 Found {len(json_files)} file(s) to convert:\n")
    for f in json_files:
        print(f"   • {f}")

    print("\n🚀 Starting conversion...\n")

    converted_count = 0
    for json_file in json_files:
        convert_json_to_csv(json_file)
        converted_count += 1

    print("\n" + "=" * 60)
    print(f"🎉 ALL DONE! Converted {converted_count} JSON file(s) to CSV.")
    print("   Check the folder — each JSON now has its matching .csv")
    print("=" * 60)
