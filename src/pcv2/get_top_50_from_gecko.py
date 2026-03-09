import requests
from datetime import datetime

def get_top_non_stable_coins(limit: int = 50, vs_currency: str = "usd"):
    """
    Returns exactly 'limit' non-stablecoins by market cap.
    Automatically saves a beautiful TXT file too.
    """
    # Current major stablecoin CoinGecko IDs (update this set occasionally)
    STABLE_IDS = {
        'tether', 'usd-coin', 'usds', 'ethena-usde', 'dai',
        'paypal-usd', 'first-digital-usd', 'true-usd', 'usdd', 'frax'
    }

    # Fetch more than we need
    params = {
        'vs_currency': vs_currency,
        'order': 'market_cap_desc',
        'per_page': limit + 60,
        'page': 1,
        'sparkline': False,
        'price_change_percentage': '24h'
    }

    url = "https://api.coingecko.com/api/v3/coins/markets"
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    filtered = []
    skipped = 0

    for coin in data:
        coin_id = coin['id']
        price = coin.get('current_price') or 0
        symbol = coin.get('symbol', '').lower()
        name = coin.get('name', '').lower()

        # Skip stables
        if coin_id in STABLE_IDS:
            skipped += 1
            continue
        if 0.92 < price < 1.08 and ('usd' in symbol or 'usd' in name):
            skipped += 1
            continue

        filtered.append(coin)
        if len(filtered) >= limit:
            break

    print(f"✅ Fetched {len(data)} coins • Skipped {skipped} stablecoins • Returning top {len(filtered)} non-stables\n")

    # Console print (top 5 only)
    print(f"{'Rank':<4} {'Name':<22} {'Symbol':<8} {'Price':>12} {'Market Cap':>18}")
    print("-" * 82)
    for rank, coin in enumerate(filtered[:5], 1):
        print(f"{rank:<4} {coin['name']:<22} {coin['symbol'].upper():<8} "
              f"${coin['current_price']:>11,.4f}   ${coin['market_cap']:>15,.0f}")

    # ====================== SAVE TO TXT ======================
    filename = f"top_{limit}_non_stable_coins.txt"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # your local time (KST on your machine)

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Top {limit} Non-Stablecoins by Market Cap ({vs_currency.upper()})\n")
        f.write(f"Generated: {timestamp}\n")
        f.write(f"Skipped stablecoins: {skipped}\n\n")
        
        f.write(f"{'Rank':<4} {'Name':<22} {'Symbol':<8} {'Price (USD)':>14} {'Market Cap':>12} {'24h %':>8}\n")
        f.write("-" * 92 + "\n")
        
        for rank, coin in enumerate(filtered, 1):
            price = coin.get('current_price', 0)
            mc = coin.get('market_cap', 0)
            change = coin.get('price_change_percentage_24h') or 0.0
            
            # Nice T/B/M formatting
            if mc >= 1_000_000_000_000:
                mc_str = f"${mc/1_000_000_000_000:.3f}T"
            elif mc >= 1_000_000_000:
                mc_str = f"${mc/1_000_000_000:.2f}B"
            else:
                mc_str = f"${mc/1_000_000:.1f}M"
                
            f.write(f"{rank:<4} {coin['name']:<22} {coin['symbol'].upper():<8} "
                    f"${price:>11,.2f}   {mc_str:>12}   {change:>7.2f}%\n")
    
    print(f"💾 Saved full list to: {filename}")
    # ====================== END SAVE ======================

    return filtered


# ==================== RUN IT ====================
if __name__ == "__main__":
    top_50 = get_top_non_stable_coins(limit=50)   # change to 100, 200, etc. if you want
