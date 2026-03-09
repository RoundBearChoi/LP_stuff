import urllib.request
import json
from urllib.error import URLError, HTTPError

# ====================== API KEY PROMPT ======================
print("🔑 CryptoCompare API Key Setup")
print("   (Free keys available at https://www.cryptocompare.com/cryptopian/api-keys)")
api_key = input("   Enter your API key (or press Enter to skip): ").strip()

# ====================== FETCH FUNCTION (FIXED) ======================
def fetch_top_symbols(page: int, api_key: str) -> list[str]:
    """
    Fetches one page (max 100 coins) from CryptoCompare.
    Now uses robust success check (API format changed).
    """
    url = f"https://min-api.cryptocompare.com/data/top/mktcapfull?limit=100&tsym=USD&page={page}"
    if api_key:
        url += f"&api_key={api_key}"
    
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            # FIXED: Check for actual Data list instead of "Response" key
            if isinstance(data.get("Data"), list):
                symbols = [coin["CoinInfo"]["Name"] for coin in data.get("Data", [])]
                print(f"✅ Page {page} → {len(symbols)} symbols fetched")
                return symbols
            else:
                msg = data.get("Message", "Unknown error")
                print(f"❌ API error on page {page}: {msg}")
                return []
                
    except (URLError, HTTPError) as e:
        print(f"❌ Network error on page {page}: {e}")
        return []
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON response on page {page}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error on page {page}: {e}")
        return []


# ========================= CONFIG =========================
NUM_PAGES = 3                    # ← Change to 5 for top 500, 10 for top 1,000, etc.
OUTPUT_TXT = f"top_{NUM_PAGES*100}_symbols.txt"
OUTPUT_JSON = f"top_{NUM_PAGES*100}_symbols.json"
# =========================================================

print("\n🚀 Starting fetch of top", NUM_PAGES * 100, "coins from CryptoCompare...\n")

all_symbols = []
for page in range(NUM_PAGES):
    page_symbols = fetch_top_symbols(page, api_key)
    all_symbols.extend(page_symbols)

# Remove any accidental duplicates while preserving order
all_symbols = list(dict.fromkeys(all_symbols))

print("\n" + "="*60)
print(f"✅ DONE! Fetched {len(all_symbols)} unique symbols (top ~{NUM_PAGES*100} by market cap)")
print("="*60)
print("Top 10  :", all_symbols[:10])
print("Rank 100:", all_symbols[99] if len(all_symbols) > 99 else "N/A")
print("Bottom 10:", all_symbols[-10:])
print("\n💾 Files saved:")

# Save to TXT (one symbol per line)
with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
    f.write("\n".join(all_symbols))
print(f"   • {OUTPUT_TXT}")

# Save to JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(all_symbols, f, indent=2)
print(f"   • {OUTPUT_JSON}")

print("\n🎉 All set! You now have the full list.")
if api_key:
    print("   🔑 API key was used — higher limits active.")
else:
    print("   ⚠️  No API key used (still works fine).")
