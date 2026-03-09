import requests
from datetime import datetime
import sys
import unicodedata   # ← Added for cleaning invisible chars


class TopNonStableCoinsFetcher:
    """
    Fetches top non-stablecoins from CoinGecko by market cap.
    Handles stablecoin skipping, CUSTOM exclusions, name/symbol truncation,
    invisible Unicode cleaning, and saves a perfectly aligned TXT report.
    """
    # Current major stablecoin CoinGecko IDs (update occasionally)
    STABLE_IDS = {
        'tether', 'usd-coin', 'usds', 'ethena-usde', 'dai',
        'paypal-usd', 'first-digital-usd', 'true-usd', 'usdd', 'frax'
    }

    # ← NEW: Coins you want to completely exclude (add more here anytime)
    # Use exact CoinGecko IDs (lowercase, as returned by the API)
    EXCLUDED_IDS = {
        'figure-heloc',
        # 'some-other-coin-id',      # ← just add lines like this in the future
        # 'yet-another-token',
    }

    MAX_NAME_LEN = 19
    MAX_SYMBOL_LEN = 12

    def __init__(self, vs_currency: str = "usd"):
        self.vs_currency = vs_currency.upper()

    def _sanitize(self, text: str) -> str:
        """Remove invisible Unicode characters (zero-width spaces, etc.) that break alignment."""
        if not text:
            return ""
        cleaned = ''.join(
            c for c in text
            if unicodedata.category(c) not in {'Cf', 'Cc', 'Zl', 'Zp'}
        )
        return cleaned.strip()

    def _truncate_name(self, name: str) -> str:
        """Truncate long names after cleaning."""
        name = self._sanitize(name)
        if len(name) > self.MAX_NAME_LEN:
            return name[:self.MAX_NAME_LEN - 3] + "..."
        return name

    def _truncate_symbol(self, symbol: str) -> str:
        """Truncate long symbols after cleaning."""
        symbol = self._sanitize(symbol)
        if len(symbol) > self.MAX_SYMBOL_LEN:
            return symbol[:self.MAX_SYMBOL_LEN - 3] + "..."
        return symbol

    def fetch_and_save(self, limit: int = 50):
        """
        Fetch, filter, print, and save exactly 'limit' non-stablecoins.
        Now also respects the EXCLUDED_IDS list.
        """
        if limit < 1:
            limit = 50
            print("⚠️  Limit must be positive — defaulting to 50")

        params = {
            'vs_currency': self.vs_currency.lower(),
            'order': 'market_cap_desc',
            'per_page': min(limit + 60, 250),
            'page': 1,
            'sparkline': False,
            'price_change_percentage': '24h'
        }

        url = "https://api.coingecko.com/api/v3/coins/markets"
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        filtered = []
        skipped_stables = 0
        excluded_custom = 0

        for coin in data:
            coin_id = coin['id']
            price = coin.get('current_price') or 0
            symbol = coin.get('symbol', '').lower()
            name = coin.get('name', '').lower()

            # Skip known stables
            if coin_id in self.STABLE_IDS:
                skipped_stables += 1
                continue

            # Skip custom exclusions (figure-heloc, etc.)
            if coin_id in self.EXCLUDED_IDS:
                excluded_custom += 1
                continue

            # Additional price-based stable detection (kept as safety net)
            if 0.92 < price < 1.08 and ('usd' in symbol or 'usd' in name):
                skipped_stables += 1
                continue

            filtered.append(coin)
            if len(filtered) >= limit:
                break

        print(f"✅ Fetched {len(data)} coins • "
              f"Skipped {skipped_stables} stablecoins • "
              f"Excluded {excluded_custom} custom coins • "
              f"Returning top {len(filtered)} non-stables\n")

        # Console preview (top 5)
        print(f"{'Rank':<4} {'Name':<22} {'Symbol':<15} {'Price':>12} {'Market Cap':>18}")
        print("-" * 89)
        for rank, coin in enumerate(filtered[:5], 1):
            display_name = self._truncate_name(coin['name'])
            display_symbol = self._truncate_symbol(coin['symbol'].upper())
            print(f"{rank:<4} {display_name:<22} {display_symbol:<15} "
                  f"${coin['current_price']:>11,.4f}   ${coin['market_cap']:>15,.0f}")

        # ====================== SAVE TO TXT ======================
        filename = f"gecko_top_{limit}_non_stable_coins.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Top {limit} Non-Stablecoins by Market Cap ({self.vs_currency})\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Skipped stablecoins: {skipped_stables}\n")
            f.write(f"Excluded additional coins: {excluded_custom}\n\n")
            
            f.write(f"{'Rank':<4} {'Name':<22} {'Symbol':<15} {'Price ({})':>14} {'Market Cap':>12} {'24h %':>8}\n"
                    .format(self.vs_currency))
            f.write("-" * 99 + "\n")
            
            for rank, coin in enumerate(filtered, 1):
                display_name = self._truncate_name(coin['name'])
                display_symbol = self._truncate_symbol(coin['symbol'].upper())
                price = coin.get('current_price', 0)
                mc = coin.get('market_cap', 0)
                change = coin.get('price_change_percentage_24h') or 0.0
                
                if mc >= 1_000_000_000_000:
                    mc_str = f"${mc/1_000_000_000_000:.3f}T"
                elif mc >= 1_000_000_000:
                    mc_str = f"${mc/1_000_000_000:.2f}B"
                else:
                    mc_str = f"${mc/1_000_000:.1f}M"
                    
                f.write(f"{rank:<4} {display_name:<22} {display_symbol:<15} "
                        f"${price:>11,.2f}   {mc_str:>12}   {change:>7.2f}%\n")
        
        print(f"💾 Saved full list to: {filename}")
        return filtered


# ==================== COMMAND-LINE RUN ====================
if __name__ == "__main__":
    try:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    except (IndexError, ValueError):
        print("Usage: python get_gecko_top_coins.py [NUMBER]")
        print("       (defaults to 50 if no number given)\n")
        limit = 50

    fetcher = TopNonStableCoinsFetcher()
    top_coins = fetcher.fetch_and_save(limit)
