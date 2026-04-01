import sys
import pandas as pd
import time
from datetime import datetime
from fetch_gecko_price_history import CoinGeckoPriceFetcher

# =============================================
# CONFIGURATION - EDIT THESE DEFAULTS
# =============================================
DEFAULT_NUM_TOKENS   = 5
DEFAULT_MONTHS       = 1
DEFAULT_WAIT_SECONDS = 2
VOLUME_TOKENS_FILE   = "volume_tokens_whole_list_mar_31st.txt"
# =============================================


def main():
    # === DETERMINE NUM_TOKENS AND MONTHS ===
    if len(sys.argv) == 1:
        num_tokens = DEFAULT_NUM_TOKENS
        months = DEFAULT_MONTHS
        print(f"ℹ️  Running with CONFIG defaults → {num_tokens} tokens, {months} month(s)")
    elif len(sys.argv) == 3:
        try:
            num_tokens = int(sys.argv[1])
            months = int(sys.argv[2])
            print(f"ℹ️  Running with command-line args → {num_tokens} tokens, {months} month(s)")
        except ValueError:
            print("❌ Error: <num_tokens> and <months> must be integers.")
            sys.exit(1)
    else:
        print("Usage:")
        print("   python fetch_gecko_all_price_history.py                  # Uses CONFIG defaults")
        print("   python fetch_gecko_all_price_history.py <num_tokens> <months>")
        sys.exit(1)

    # Load token list
    try:
        df = pd.read_csv(VOLUME_TOKENS_FILE)
        print(f"✅ Loaded {len(df):,} tokens from {VOLUME_TOKENS_FILE}")
        tokens_to_process = df["symbol"].head(num_tokens).astype(str).str.strip().tolist()
        print(f"🚀 Will process first {len(tokens_to_process)} tokens for {months} month(s) each.")
    except Exception as e:
        print(f"❌ Could not load {VOLUME_TOKENS_FILE}: {e}")
        sys.exit(1)

    fetcher = CoinGeckoPriceFetcher(volume_file=VOLUME_TOKENS_FILE)

    # Load mapping ONCE
    print("\n🔄 Loading volume token mapping once for all tokens...")
    volume_mapping = fetcher.load_volume_token_mapping()

    # Ask for API key ONCE
    print("\n" + "=" * 70)
    print("🔑 CoinGecko Pro API Key (asked once for the entire batch)")
    print("=" * 70)
    api_key = fetcher.get_masked_input("API Key: ")
    if not api_key:
        print("❌ API key is required.")
        sys.exit(1)

    successful = 0
    failed = 0
    skipped = 0      # NEW: tracks pure skips (no API)
    downloaded = 0   # NEW: tracks actual API usage
    start_time = datetime.now()

    print(f"\n🏁 Starting batch processing of {len(tokens_to_process)} tokens...\n")

    for i, symbol in enumerate(tokens_to_process, 1):
        print(f"{'=' * 80}")
        print(f"[{i:3d}/{len(tokens_to_process)}] Processing → {symbol}")
        print(f"{'=' * 80}")

        fetched = False   # default for safety
        try:
            success, fetched = fetcher.run(coin_input=symbol, months=months, api_key=api_key,
                                           volume_mapping=volume_mapping)
            if success:
                successful += 1
                if fetched:
                    downloaded += 1
                else:
                    skipped += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Unexpected error on {symbol}: {e}")
            failed += 1
            fetched = False

        if i < len(tokens_to_process):
            if fetched:
                print(f"⏳ Waiting {DEFAULT_WAIT_SECONDS} seconds before next token (API was used)...")
                time.sleep(DEFAULT_WAIT_SECONDS)
            else:
                print(f"   ⏭️  Skipped (file already exists) → no wait needed")

    total_time = datetime.now() - start_time

    # === FINAL SUMMARY ===
    print(f"\n🎉 BATCH COMPLETE!")
    print(f"   ✅ Successfully processed (including skips) : {successful}")
    print(f"   ⏭️  Skipped (file already existed)          : {skipped}")
    print(f"   📥 Downloaded fresh data                    : {downloaded}")
    print(f"   ❌ Failed / not found                       : {failed}")
    print(f"   ⏱️  Total time                              : {total_time}")
    print(f"   📁 Files saved to 'price_data/' folder\n")

    print("💡 Tip: Skipped tokens show '⏭️  File already exists → skipping' in the log.")
    print("   Change FORCE_FRESH_DOWNLOAD = True in fetch_gecko_price_history.py")
    print("   if you want to force a full refresh for everything.")

if __name__ == "__main__":
    main()
