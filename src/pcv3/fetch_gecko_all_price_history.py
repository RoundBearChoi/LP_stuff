import sys
import pandas as pd
import time
from datetime import datetime
from fetch_gecko_price_history import CoinGeckoPriceFetcher

# =============================================
# CONFIGURATION - EDIT THESE DEFAULTS
# =============================================
DEFAULT_NUM_TOKENS   = 5
DEFAULT_MONTHS       = 1       # ← Change to 18 when you want full 18-month history
DEFAULT_WAIT_SECONDS = 3       # ← Seconds to wait between tokens (rate-limit safety / stability)
VOLUME_TOKENS_FILE   = "volume_tokens_whole_list_mar_31st.txt"
# =============================================


def main():
    # === DETERMINE NUM_TOKENS AND MONTHS (config vs command-line) ===
    if len(sys.argv) == 1:
        num_tokens = DEFAULT_NUM_TOKENS
        months = DEFAULT_MONTHS
        print(f"ℹ️  Running with CONFIG defaults → {num_tokens} tokens, {months} month(s), {DEFAULT_WAIT_SECONDS}s wait")
    elif len(sys.argv) == 3:
        try:
            num_tokens = int(sys.argv[1])
            months = int(sys.argv[2])
            print(f"ℹ️  Running with command-line args → {num_tokens} tokens, {months} month(s), {DEFAULT_WAIT_SECONDS}s wait")
        except ValueError:
            print("❌ Error: <num_tokens> and <months> must be integers.")
            sys.exit(1)
    else:
        print("Usage:")
        print("   python fetch_gecko_all_price_history.py                  # Uses CONFIG defaults")
        print("   python fetch_gecko_all_price_history.py <num_tokens> <months>")
        print("")
        print("Examples:")
        print("   python fetch_gecko_all_price_history.py 5 1")
        print("   python fetch_gecko_all_price_history.py 541 18")
        sys.exit(1)

    # Load the token list
    try:
        df = pd.read_csv(VOLUME_TOKENS_FILE)
        print(f"✅ Loaded {len(df):,} tokens from {VOLUME_TOKENS_FILE}")
        tokens_to_process = df["symbol"].head(num_tokens).astype(str).str.strip().tolist()
        print(f"🚀 Will process first {len(tokens_to_process)} tokens for {months} month(s) each.")
    except Exception as e:
        print(f"❌ Could not load {VOLUME_TOKENS_FILE}: {e}")
        sys.exit(1)

    fetcher = CoinGeckoPriceFetcher(volume_file=VOLUME_TOKENS_FILE)

    # Load mapping ONCE for the entire batch
    print("\n🔄 Loading volume token mapping once for all tokens...")
    volume_mapping = fetcher.load_volume_token_mapping()

    # Ask for API key ONCE (now using the simplified Linux-only masked input)
    print("\n" + "=" * 70)
    print("🔑 CoinGecko Pro API Key (asked once for the entire batch)")
    print("=" * 70)
    api_key = fetcher.get_masked_input("API Key: ")
    if not api_key:
        print("❌ API key is required.")
        sys.exit(1)

    successful = 0
    skipped = 0
    not_found_coins = []
    start_time = datetime.now()

    print(f"\n🏁 Starting batch processing of {len(tokens_to_process)} tokens...\n")

    for i, symbol in enumerate(tokens_to_process, 1):
        print(f"{'=' * 80}")
        print(f"[{i:3d}/{len(tokens_to_process)}] Processing → {symbol}")
        print(f"{'=' * 80}")

        try:
            success = fetcher.run(coin_input=symbol, months=months, api_key=api_key,
                                  volume_mapping=volume_mapping)
            if success:
                successful += 1
            else:
                not_found_coins.append(symbol)
                skipped += 1
        except SystemExit:
            print(f"⚠️  Skipped {symbol} (already up-to-date)")
            skipped += 1
        except Exception as e:
            print(f"❌ Unexpected error on {symbol}: {e}")
            skipped += 1

        if i < len(tokens_to_process):
            print(f"⏳ Waiting {DEFAULT_WAIT_SECONDS} seconds before next token...")
            time.sleep(DEFAULT_WAIT_SECONDS)

    total_time = datetime.now() - start_time

    # === FINAL SUMMARY WITH NOT-FOUND LIST ===
    print(f"\n🎉 BATCH COMPLETE!")
    print(f"   ✅ Successfully processed : {successful}")
    print(f"   ⚠️  Already up-to-date     : {skipped - len(not_found_coins)}")
    print(f"   ⏱️  Total time            : {total_time}")
    print(f"   📁 Files saved to 'price_data/' folder\n")

    if not_found_coins:
        print("=" * 60)
        print("❌ Coins NOT FOUND on CoinGecko (no CSV files created):")
        for coin in sorted(not_found_coins):
            print(f"   • {coin}")
        print(f"   Total not found: {len(not_found_coins)}")
        print("=" * 60)
        print("   Tip: These coingecko_ids may be outdated in volume_tokens_whole_list_mar_31st.txt")
    else:
        print("✅ All coins were successfully found on CoinGecko!")

if __name__ == "__main__":
    main()
