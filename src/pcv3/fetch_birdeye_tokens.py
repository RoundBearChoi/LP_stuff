import requests
import time
import json
import sys
import os

# ============== CONFIG (easy to tweak) ==============
CHAIN = "solana"
LIMIT = 100          # max 100 per call on free tier

MIN_VOLUME_24H_USD = 0
MIN_LIQUIDITY = 1_000_000
MIN_MC = 0

TARGET = 200                   # how many tokens you want (200 by default)

PAGE_WAIT_SECONDS = 1.1        # ← NEW: seconds to wait BEFORE each new page
                               # Free tier: 1.1 is safe. Paid tier: can go down to 0.0
# ========================================================

def masked_input(prompt="Enter your Birdeye API key: ", mask="*"):
    """Get hidden input while displaying a mask character (e.g. ****).
    Cross-platform (Windows + Linux/macOS)."""
    print(prompt, end="", flush=True)
    password = ""

    if os.name == "nt":  # Windows
        import msvcrt
        while True:
            char = msvcrt.getch()
            if char in (b"\r", b"\n"):          # Enter key
                print()  # new line
                break
            elif char == b"\x08":               # Backspace
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
                if ch in ("\r", "\n"):          # Enter
                    print()
                    break
                elif ch == "\x7f":              # Backspace (Unix)
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
    
    print()                                 # clean left-aligned line
    if not api_key:
        print("❌ API key cannot be empty. Exiting.")
        exit(1)
    
    print("✅ API key received (masked for security)\n")
    return api_key


def format_money(amount):
    """Pretty-format large USD numbers (crypto style)"""
    if amount >= 1_000_000_000_000:   # Trillions
        return f"${amount/1_000_000_000_000:.2f}T"
    elif amount >= 1_000_000_000:     # Billions
        return f"${amount/1_000_000_000:.2f}B"
    elif amount >= 1_000_000:         # Millions
        return f"${amount/1_000_000:.2f}M"
    else:
        return f"${amount:,.0f}"


def fetch_highest_volume_gems(api_key, offset=0, limit=LIMIT, sort_by="volume_24h_usd"):
    url = "https://public-api.birdeye.so/defi/v3/token/list"
    
    params = {
        "sort_by": sort_by,
        "sort_type": "desc",
        "offset": offset,
        "limit": limit,
        "ui_amount_mode": "scaled",
    }
    
    # ==================== CONDITIONAL FILTERS ====================
    # Only send the parameter if the config value is > 0
    # (Birdeye API errors on min_volume_24h_usd=0 and treats omitted params as "no filter")
    if MIN_VOLUME_24H_USD > 0:
        params["min_volume_24h_usd"] = MIN_VOLUME_24H_USD
    if MIN_LIQUIDITY > 0:
        params["min_liquidity"] = MIN_LIQUIDITY
    if MIN_MC > 0:
        params["min_mc"] = MIN_MC
    # ============================================================
    
    headers = {
        "accept": "application/json",
        "x-chain": CHAIN,
        "X-API-KEY": api_key
    }
    
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            return data["data"]["items"]
        else:
            print("API error:", data.get("message", data))
            return []
    elif response.status_code == 429:
        print("⏳ Rate limited – waiting 1.1s...")
        time.sleep(1.1)
        return fetch_highest_volume_gems(api_key, offset, limit, sort_by)
    else:
        print(f"Error {response.status_code}: {response.text}")
        return []


# ============== MAIN PROGRAM ==============
if __name__ == "__main__":
    # 1. Ask for API key with masking
    API_KEY = get_api_key()
    
    PAGE_SIZE = 100                  # free tier max
    
    print(f"🚀 Fetching top {TARGET} highest 24h volume gems on {CHAIN.upper()}...")
    
    # Build nice dynamic filter text (only shows active filters)
    active_filters = []
    if MIN_VOLUME_24H_USD > 0:
        active_filters.append(f"≥${MIN_VOLUME_24H_USD:,} vol")
    if MIN_LIQUIDITY > 0:
        active_filters.append(f"≥${MIN_LIQUIDITY:,} liq")
    if MIN_MC > 0:
        active_filters.append(f"≥${MIN_MC:,} MC")
    
    filter_text = " | ".join(active_filters) if active_filters else "No minimum filters (all tokens)"
    
    print(f"   Filters: {filter_text}")
    print(f"   Page wait time: {PAGE_WAIT_SECONDS}s between pages\n")
    
    all_gems = []
    offset = 0
    
    while len(all_gems) < TARGET:
        # ── Wait time BEFORE each page (except the very first call) ──
        if offset > 0:
            print(f"   ⏳ Waiting {PAGE_WAIT_SECONDS}s before next page...")
            time.sleep(PAGE_WAIT_SECONDS)
        
        needed = TARGET - len(all_gems)
        limit = min(PAGE_SIZE, needed)
        
        print(f"   Fetching page offset={offset} (limit={limit})...")
        page = fetch_highest_volume_gems(API_KEY, offset=offset, limit=limit, sort_by="volume_24h_usd")
        
        if not page:
            print("   No more data returned.")
            break
        
        all_gems.extend(page)
        offset += len(page)
    
    gems = all_gems[:TARGET]   # trim if we somehow overshot
    
    # 3. Pretty print top 10
    if gems:
        print(f"\n📊 Top {min(10, len(gems))} Highest 24h Volume Tokens on {CHAIN.upper()}\n")
        
        # Header
        print(f"{'Rank':<4} {'Symbol':<10} {'24h Vol':<13} {'Market Cap':<14} {'FDV':<14} {'Liquidity':<14}")
        print("-" * 78)
        
        for i, token in enumerate(gems[:10], 1):
            mc = token.get('market_cap') or token.get('mc', 0)
            fdv = token.get('fdv', 0)
            vol = token.get('volume_24h_usd', 0)
            liq = token.get('liquidity', 0)
            
            print(f"{i:<4} {token.get('symbol', 'N/A'):<10} "
                  f"{format_money(vol):<13} "
                  f"{format_money(mc):<14} "
                  f"{format_money(fdv):<14} "
                  f"{format_money(liq):<14}")
        
        # 4. Save full results to JSON
        filename = f"highest_volume_gems_{CHAIN}_{TARGET}.json"
        with open(filename, "w") as f:
            json.dump(gems, f, indent=2)
        
        print(f"\n✅ Success! Saved {len(gems)} tokens to → {filename}")
    else:
        print("❌ No data returned. Try lowering the filters or check your API key/rate limits.")
