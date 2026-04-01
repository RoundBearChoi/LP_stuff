import requests
import pandas as pd
from collections import defaultdict
import sys
import tty
import termios


# =============== CONFIG SECTION ===============
# Exchange IDs (official CoinGecko IDs)
MEXC_EXCHANGE_ID = "mxc"       # MEXC
KUCOIN_EXCHANGE_ID = "kucoin"  # KuCoin

# Max pages to fetch (CoinGecko returns up to 100 tickers per page)
MEXC_MAX_PAGES = 1
KUCOIN_MAX_PAGES = 1

# Output CSV filenames (change if you want different names/paths)
MEXC_OUTPUT_CSV = "gecko_mexc_top_tokens_24h.csv"
KUCOIN_OUTPUT_CSV = "gecko_kucoin_top_tokens_24h.csv"

# How many tokens to DISPLAY in the console (only affects printing, not CSV)
PRINT_TOP = 5
# ==============================================


def masked_input(prompt: str = "") -> str:
    """Read input with * masking shown in REAL-TIME (as you type OR paste).
    Supports backspace. Now also forces clean newline on Enter (bonus fix)."""
    if prompt:
        print(prompt, end="", flush=True)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    password = ""

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):          # Enter pressed
                # Bonus: Force cursor to column 0 + new line (prevents indent bug)
                print("\033[0G\n", end="", flush=True)
                break
            elif ch == "\x7f":              # Backspace
                if password:
                    password = password[:-1]
                    print("\b \b", end="", flush=True)
            else:
                password += ch
                print("*", end="", flush=True)   # ← * appears instantly
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return password.strip()


def get_exchange_tickers(exchange_id: str, api_key: str, max_pages: int = 30) -> list:
    """Fetch all tickers (paginated) for an exchange. Returns raw list."""
    url = f"https://pro-api.coingecko.com/api/v3/exchanges/{exchange_id}/tickers"
    headers = {"x-cg-pro-api-key": api_key}
    params = {"order": "volume_desc", "page": 1}

    all_tickers = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        tickers = data.get("tickers", [])
        all_tickers.extend(tickers)
        if len(tickers) < 100:  # last page reached
            break
    return all_tickers


def aggregate_volume_per_token(tickers: list) -> pd.DataFrame:
    """Aggregate 24h USD volume per coin_id. Returns ALL tokens received (no limit)."""
    token_volume: defaultdict[float] = defaultdict(float)
    token_pairs: defaultdict[list] = defaultdict(list)
    token_names: dict[str, str] = {}  # coin_id -> name

    for t in tickers:
        coin_id = t.get("coin_id")
        if not coin_id:
            continue
        vol_usd = t.get("converted_volume", {}).get("usd", 0)
        if isinstance(vol_usd, (int, float)):
            token_volume[coin_id] += vol_usd
            token_pairs[coin_id].append(f"{t['base']}/{t['target']}")
            if coin_id not in token_names:
                token_names[coin_id] = t.get("base", coin_id)  # fallback

    df = pd.DataFrame({
        "coin_id": list(token_volume.keys()),
        "token_name": [token_names.get(cid, cid) for cid in token_volume.keys()],
        "total_24h_volume_usd": list(token_volume.values()),
        "pairs_count": [len(token_pairs[cid]) for cid in token_volume.keys()],
        "example_pairs": [", ".join(token_pairs[cid][:3]) for cid in token_volume.keys()]
    })

    # Sort by volume (descending) — keep EVERY token that was received
    df = df.sort_values("total_24h_volume_usd", ascending=False).copy()
    df["total_24h_volume_usd"] = df["total_24h_volume_usd"].apply(lambda x: f"${x:,.0f}")
    return df.reset_index(drop=True)


# =============== MAIN EXECUTION ===============
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 CoinGecko 24h Volume Aggregator")
    print("   → Aggregates per-token 24h USD volume on MEXC + KuCoin")
    print("   → Uses your paid Basic-tier API key")
    print("=" * 60)

    # Real-time masked input — * appear instantly while you copy-paste or type
    api_key = masked_input("\n🔑 Enter your CoinGecko Pro API key: ")
    print()  # ← Quick fix: guarantees clean line after input (extra safety)

    if not api_key:
        print("❌ Error: API key cannot be empty. Exiting.")
        sys.exit(1)

    # MEXC
    print(f"📡 Fetching {MEXC_EXCHANGE_ID.upper()} tickers (this may take a few seconds)...")
    mexc_tickers = get_exchange_tickers(MEXC_EXCHANGE_ID, api_key, max_pages=MEXC_MAX_PAGES)
    mexc_df = aggregate_volume_per_token(mexc_tickers)

    print(f"\n=== {MEXC_EXCHANGE_ID.upper()} — Top {PRINT_TOP} Tokens by 24h USD Volume ===")
    print(mexc_df.head(PRINT_TOP).to_string(index=False))

    # KuCoin
    print(f"\n📡 Fetching {KUCOIN_EXCHANGE_ID.upper()} tickers (this may take a few seconds)...")
    kucoin_tickers = get_exchange_tickers(KUCOIN_EXCHANGE_ID, api_key, max_pages=KUCOIN_MAX_PAGES)
    kucoin_df = aggregate_volume_per_token(kucoin_tickers)

    print(f"\n=== {KUCOIN_EXCHANGE_ID.upper()} — Top {PRINT_TOP} Tokens by 24h USD Volume ===")
    print(kucoin_df.head(PRINT_TOP).to_string(index=False))

    # Save EVERYTHING received to CSV
    mexc_df.to_csv(MEXC_OUTPUT_CSV, index=False)
    kucoin_df.to_csv(KUCOIN_OUTPUT_CSV, index=False)

    print("\n💾 Full results saved to:")
    print(f"   → {MEXC_OUTPUT_CSV}  ({len(mexc_df):,} tokens)")
    print(f"   → {KUCOIN_OUTPUT_CSV}  ({len(kucoin_df):,} tokens)")

    print("\n✅ Done! Run again anytime for fresh 24h data.")
