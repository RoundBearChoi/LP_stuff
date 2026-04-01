import requests
import pandas as pd
from collections import defaultdict
import sys
import tty
import termios


# =============== CONFIG SECTION ===============
# Top DEX IDs (get more from https://www.coingecko.com/en/exchanges/decentralized — use the URL slug)
DEX_EXCHANGE_IDS = [
    "aerodrome-base",
    "aerodrome-slipstream",
    "aerodrome-slipstream-2",
    "uniswap_v3",
]

MAX_PAGES_PER_DEX = 1

# Use symbol format for pairs on DEX (cleaner than contract addresses)
DEX_PAIR_FORMAT = "symbol"   # "symbol" or "contract_address"

# Output CSV filenames
COMBINED_OUTPUT_CSV = "gecko_top_dexes_aggregated_tokens_24h.csv"
PER_DEX_OUTPUT_PREFIX = "gecko_dex_"   # e.g. gecko_dex_uniswap-v3-ethereum_24h.csv

# How many tokens to DISPLAY in console
PRINT_TOP = 10
# ==============================================


def masked_input(prompt: str = "") -> str:
    """Read input with * masking (same as your original)."""
    if prompt:
        print(prompt, end="", flush=True)

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    password = ""

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                print("\033[0G\n", end="", flush=True)
                break
            elif ch == "\x7f":
                if password:
                    password = password[:-1]
                    print("\b \b", end="", flush=True)
            else:
                password += ch
                print("*", end="", flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return password.strip()


def get_exchange_tickers(exchange_id: str, api_key: str, max_pages: int = 30) -> list:
    """Fetch tickers (paginated) — works for both CEX and DEX."""
    url = f"https://pro-api.coingecko.com/api/v3/exchanges/{exchange_id}/tickers"
    headers = {"x-cg-pro-api-key": api_key}
    params = {
        "order": "volume_desc",
        "page": 1,
        "dex_pair_format": DEX_PAIR_FORMAT if "dex" in exchange_id.lower() or exchange_id in DEX_EXCHANGE_IDS else None
    }

    all_tickers = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        tickers = data.get("tickers", [])
        all_tickers.extend(tickers)
        if len(tickers) < 100:
            break
    return all_tickers


def aggregate_volume_per_token(tickers: list, label: str = "") -> pd.DataFrame:
    """Aggregate 24h USD volume per coin_id (same logic as your script)."""
    token_volume: defaultdict[float] = defaultdict(float)
    token_pairs: defaultdict[list] = defaultdict(list)
    token_names: dict[str, str] = {}

    for t in tickers:
        coin_id = t.get("coin_id")
        if not coin_id:
            continue
        vol_usd = t.get("converted_volume", {}).get("usd", 0)
        if isinstance(vol_usd, (int, float)):
            token_volume[coin_id] += vol_usd
            token_pairs[coin_id].append(f"{t.get('base', '')}/{t.get('target', '')}")
            if coin_id not in token_names:
                token_names[coin_id] = t.get("base", coin_id)

    df = pd.DataFrame({
        "coin_id": list(token_volume.keys()),
        "token_name": [token_names.get(cid, cid) for cid in token_volume.keys()],
        "total_24h_volume_usd": list(token_volume.values()),
        "pairs_count": [len(token_pairs[cid]) for cid in token_volume.keys()],
        "example_pairs": [", ".join(token_pairs[cid][:3]) for cid in token_volume.keys()],
        "source": label
    })

    df = df.sort_values("total_24h_volume_usd", ascending=False).copy()
    df["total_24h_volume_usd"] = df["total_24h_volume_usd"].apply(lambda x: f"${x:,.0f}")
    return df.reset_index(drop=True)


# =============== MAIN EXECUTION ===============
if __name__ == "__main__":
    print("=" * 70)
    print("🚀 CoinGecko DEX 24h Volume Aggregator (Basic Pro Tier)")
    print("   → Top tokens by 24h USD volume across selected DEXes")
    print("   → Per-DEX + Combined aggregate")
    print("=" * 70)

    api_key = masked_input("\n🔑 Enter your CoinGecko Pro API key: ")
    print()

    if not api_key:
        print("❌ Error: API key cannot be empty.")
        sys.exit(1)

    all_dfs = []
    combined_tickers = []

    for dex_id in DEX_EXCHANGE_IDS:
        print(f"📡 Fetching {dex_id.upper()} tickers ({MAX_PAGES_PER_DEX} pages max)...")
        tickers = get_exchange_tickers(dex_id, api_key, max_pages=MAX_PAGES_PER_DEX)
        df = aggregate_volume_per_token(tickers, label=dex_id)

        print(f"\n=== {dex_id.upper()} — Top {PRINT_TOP} Tokens by 24h USD Volume ===")
        print(df.head(PRINT_TOP).to_string(index=False))

        # Save per-DEX CSV
        csv_name = f"{PER_DEX_OUTPUT_PREFIX}{dex_id}_24h.csv"
        df.to_csv(csv_name, index=False)
        print(f"   💾 Saved {len(df):,} tokens → {csv_name}")

        all_dfs.append(df)
        combined_tickers.extend(tickers)

    # === Combined aggregate across ALL selected DEXes ===
    print("\n🔄 Aggregating top tokens ACROSS ALL DEXes...")
    combined_df = aggregate_volume_per_token(combined_tickers, label="ALL_DEXES")
    combined_df.to_csv(COMBINED_OUTPUT_CSV, index=False)

    print(f"\n=== TOP {PRINT_TOP} TOKENS ACROSS ALL SELECTED DEXES (24h USD Volume) ===")
    print(combined_df.head(PRINT_TOP).to_string(index=False))
    print(f"\n💾 Full cross-DEX aggregate saved → {COMBINED_OUTPUT_CSV} ({len(combined_df):,} tokens)")

    print("\n✅ Done! Run again anytime. Results reflect latest on-chain volume.")
