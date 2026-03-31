import requests
import time
import json
import sys
import os

# ============== CONFIG (easy to tweak) ==============
CHAINS = ["solana", "base", "bsc", "ethereum"]

LIMIT = 100          # max 100 per call on free tier

MIN_VOLUME_24H_USD = 100_000
MIN_LIQUIDITY = 1_000_000
MIN_MC = 1_000_000

TARGET_PER_CHAIN = 200          # how many tokens to fetch from EACH chain

# Rate-limit backoff
RATE_LIMIT_WAIT_SECONDS = 5.0
PAGE_WAIT_SECONDS = 1.1         # proactive wait before each new page
# ========================================================

def masked_input(prompt="Enter your Birdeye API key: ", mask="*"):
    """Get hidden input while displaying a mask character (e.g. ****). Cross-platform."""
    print(prompt, end="", flush=True)
    password = ""

    if os.name == "nt":  # Windows
        import msvcrt
        while True:
            char = msvcrt.getch()
            if char in (b"\r", b"\n"):
                print()
                break
            elif char == b"\x08":
                if password:
                    password = password[:-1]
                    print("\b \b", end="", flush=True)
            else:
                password += char.decode("utf-8", errors="ignore")
                print(mask, end="", flush=True)
    else:  # Unix / macOS / Linux
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch in ("\r", "\n"):
                    print()
                    break
                elif ch == "\x7f":
                    if password:
                        password = password[:-1]
                        print("\b \b", end="", flush=True)
                else:
                    password += ch
                    print(mask, end="", flush=True)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    return password.strip()


def get_api_key():
    """Ask user for Birdeye API key with visible masking (****)."""
    print("\n🔑 Birdeye API Key Required (free tier works perfectly)")
    print("   (Your key will be hidden as you type – shown as ****)\n")
    
    api_key = masked_input("Enter your Birdeye API key: ")
    
    print()
    if not api_key:
        print("❌ API key cannot be empty. Exiting.")
        exit(1)
    
    print("✅ API key received (masked for security)\n")
    return api_key


def format_money(amount):
    """Pretty-format large USD numbers (crypto style)"""
    if amount >= 1_000_000_000_000:
        return f"${amount/1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:
        return f"${amount/1_000_000_000:.2f}B"
    elif amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    else:
        return f"${amount:,.0f}"


def fetch_highest_volume_gems(api_key, chain, offset=0, limit=LIMIT, sort_by="volume_24h_usd"):
    """Fetch one page from Birdeye. Accepts `chain` as argument."""
    url = "https://public-api.birdeye.so/defi/v3/token/list"
    
    params = {
        "sort_by": sort_by,
        "sort_type": "desc",
        "offset": offset,
        "limit": limit,
        "ui_amount_mode": "scaled",
    }
    
    if MIN_VOLUME_24H_USD > 0:
        params["min_volume_24h_usd"] = MIN_VOLUME_24H_USD
    if MIN_LIQUIDITY > 0:
        params["min_liquidity"] = MIN_LIQUIDITY
    if MIN_MC > 0:
        params["min_mc"] = MIN_MC
    
    headers = {
        "accept": "application/json",
        "x-chain": chain,
        "X-API-KEY": api_key
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data["data"]["items"]
        else:
            print(f"   API error on {chain}: {data.get('message', data)}")
            return []
    elif response.status_code == 429:
        print(f"   ⏳ Rate limited on {chain} – waiting {RATE_LIMIT_WAIT_SECONDS}s...")
        time.sleep(RATE_LIMIT_WAIT_SECONDS)
        return fetch_highest_volume_gems(api_key, chain, offset, limit, sort_by)
    else:
        print(f"   Error {response.status_code} on {chain}: {response.text}")
        return []


def print_top_tokens(tokens, chain):
    """Print top 10 for a specific chain."""
    if not tokens:
        return
    print(f"\n📊 Top 10 Highest 24h Volume Tokens – {chain.upper()}\n")
    print(f"{'Rank':<4} {'Symbol':<10} {'24h Vol':<13} {'Market Cap':<14} {'FDV':<14} {'Liquidity':<14}")
    print("-" * 70)
    
    for i, token in enumerate(tokens[:10], 1):
        mc = token.get('market_cap') or token.get('mc', 0)
        fdv = token.get('fdv', 0)
        vol = token.get('volume_24h_usd', 0)
        liq = token.get('liquidity', 0)
        
        print(f"{i:<4} {token.get('symbol', 'N/A'):<10} "
              f"{format_money(vol):<13} "
              f"{format_money(mc):<14} "
              f"{format_money(fdv):<14} "
              f"{format_money(liq):<14}")


# ============== MAIN PROGRAM ==============
if __name__ == "__main__":
    try:
        # 1. Ask for API key
        API_KEY = get_api_key()
        PAGE_SIZE = 100
        
        print(f"🚀 Fetching top {TARGET_PER_CHAIN} highest 24h volume gems **per chain** (one chain at a time)...")
        print(f"   Chains: {', '.join(c.upper() for c in CHAINS)}")
        
        # Build filter text
        active_filters = []
        if MIN_VOLUME_24H_USD > 0:
            active_filters.append(f">=${MIN_VOLUME_24H_USD:,} vol")
        if MIN_LIQUIDITY > 0:
            active_filters.append(f">=${MIN_LIQUIDITY:,} liq")
        if MIN_MC > 0:
            active_filters.append(f">=${MIN_MC:,} MC")
        filter_text = " | ".join(active_filters) if active_filters else "No minimum filters (all tokens)"
        
        print(f"   Filters: {filter_text}")
        print(f"   Page wait: {PAGE_WAIT_SECONDS}s | Rate-limit wait: {RATE_LIMIT_WAIT_SECONDS}s\n")
        
        # ── Process one chain at a time ──
        for chain in CHAINS:
            print(f"🔄 Processing chain: {chain.upper()}")
            
            gems_this_chain = []
            offset = 0
            
            while len(gems_this_chain) < TARGET_PER_CHAIN:
                if offset > 0:
                    print(f"   ⏳ Waiting {PAGE_WAIT_SECONDS}s before next page...")
                    time.sleep(PAGE_WAIT_SECONDS)
                
                needed = TARGET_PER_CHAIN - len(gems_this_chain)
                limit = min(PAGE_SIZE, needed)
                
                print(f"   Fetching page offset={offset} (limit={limit})...")
                page = fetch_highest_volume_gems(API_KEY, chain=chain, offset=offset, limit=limit)
                
                if not page:
                    print(f"   No more data returned from {chain}.")
                    break
                
                for token in page:
                    token["chain"] = chain
                
                gems_this_chain.extend(page)
                offset += len(page)
            
            # Trim to exact target
            gems_this_chain = gems_this_chain[:TARGET_PER_CHAIN]
            
            print(f"   ✅ Got {len(gems_this_chain)} tokens from {chain.upper()}")
            
            # Show top 10
            print_top_tokens(gems_this_chain, chain)
            
            # Save JSON for this chain only
            filename = f"highest_volume_gems_{chain}_{len(gems_this_chain)}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(gems_this_chain, f, indent=2)
            
            print(f"   💾 Saved {len(gems_this_chain)} tokens → {filename}\n")
        
        print("🎉 All chains completed! Check your folder for the individual JSON files.")

    except Exception as e:
        print(f"\n❌ CRASH DETECTED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Tip: Delete the file completely and copy the entire script above again.")
        print("   Make sure your editor saves it as UTF-8 (most do by default).")
        sys.exit(1)
