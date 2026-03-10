import requests
from datetime import datetime
import sys
import unicodedata
import time
import os

class TopNonStableCoinsFetcher:
    """
    Fetches top non-stablecoins from CoinGecko by market cap.
    Interactive API key prompt + automatic retry on 429.
    Main list is now ultra-clean (no custom exclusion list/note).
    """
    STABLE_IDS = {
        'tether', 'usd-coin', 'usds', 'ethena-usde', 'dai',
        'paypal-usd', 'first-digital-usd', 'true-usd', 'usdd', 'frax'
    }

    EXCLUDED_IDS = {
        'figure-heloc',
        'hashnote-usyc',
        'superstate-short-duration-us-government-securities-fund-ustb',
        'eutbl',
        'janus-henderson-anemoy-aaa-clo-fund',
        'ylds',
        'janus-henderson-anemoy-treasury-fund',
        'eurc',
        
        # Newly added (March 2026):
        #'rain',           # RAIN
        #'mantle',         # MNT (Mantle L2)
        #'pi-network',     # PI (Pi Network)
        'ousg',           # OUSG (tokenized T-bills)
        'a7a5',           # A7A5
        'kinesis-gold',   # KAU (gold-backed)
        'usx',            # USX
    }

    MAX_NAME_LEN = 19
    MAX_SYMBOL_LEN = 12

    def __init__(self, vs_currency: str = "usd"):
        self.vs_currency = vs_currency.upper()

    def _sanitize(self, text: str) -> str:
        if not text:
            return ""
        cleaned = ''.join(
            c for c in text
            if unicodedata.category(c) not in {'Cf', 'Cc', 'Zl', 'Zp'}
        )
        return cleaned.strip()

    def _truncate_name(self, name: str) -> str:
        name = self._sanitize(name)
        if len(name) > self.MAX_NAME_LEN:
            return name[:self.MAX_NAME_LEN - 3] + "..."
        return name

    def _truncate_symbol(self, symbol: str) -> str:
        symbol = self._sanitize(symbol)
        if len(symbol) > self.MAX_SYMBOL_LEN:
            return symbol[:self.MAX_SYMBOL_LEN - 3] + "..."
        return symbol

    def _make_request_with_retry(self, url, params, headers, max_retries=3):
        for attempt in range(max_retries + 1):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=30)
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    wait = min(retry_after, 30 * (2 ** attempt))
                    print(f"⚠️  Rate limited (429). Waiting {wait}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if getattr(response, 'status_code', 0) == 429 and attempt < max_retries:
                    continue
                print(f"❌ API error: {e}")
                raise
            except requests.exceptions.RequestException as e:
                print(f"❌ Network error: {e}")
                if attempt < max_retries:
                    time.sleep(10 * (2 ** attempt))
                    continue
                raise
        raise requests.exceptions.HTTPError("Max retries exceeded for rate limit")

    def _save_excluded_report(self, excluded, skipped_stables, excluded_custom, limit):
        filename = f"gecko_excluded_{limit}_coins.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S KST")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(f"Excluded Coins Report (from top {len(excluded) + limit} fetched)\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Total skipped stablecoins: {skipped_stables}\n")
            f.write(f"Total custom excluded (RWAs + euro + requested blacklist): {excluded_custom}\n")
            f.write(f"Total excluded: {len(excluded)}\n\n")

            f.write(f"{'Orig Rank':<10} {'Name':<30} {'Symbol':<12} {'Price ({})':>14} "
                    f"{'Market Cap':>15} {'Reason':<30}\n".format(self.vs_currency))
            f.write("-" * 110 + "\n")

            for orig_rank, coin, reason in excluded:
                display_name = self._truncate_name(coin['name'])
                display_symbol = self._truncate_symbol(coin['symbol'].upper())
                price = coin.get('current_price', 0)
                mc = coin.get('market_cap', 0)
                mc_str = (f"${mc/1_000_000_000_000:.3f}T" if mc >= 1e12 else
                         f"${mc/1_000_000_000:.2f}B" if mc >= 1e9 else
                         f"${mc/1_000_000:.1f}M")
                f.write(f"{orig_rank:<10} {display_name:<30} {display_symbol:<12} "
                        f"${price:>11,.2f}   {mc_str:>15}   {reason:<30}\n")
        print(f"📄 Saved excluded report to: {filename}")

    def fetch_and_save(self, limit: int = 50):
        if limit < 1:
            limit = 50

        params = {
            'vs_currency': self.vs_currency.lower(),
            'order': 'market_cap_desc',
            'per_page': min(limit + 60, 250),
            'page': 1,
            'sparkline': False,
            'price_change_percentage': '24h'
        }

        # === INTERACTIVE API KEY PROMPT ===
        api_key = os.getenv("COINGECKO_API_KEY")
        if api_key:
            print(f"🔑 Using CoinGecko Demo API key from environment variable")
        else:
            print("\n🔑 CoinGecko Demo API key (free tier)")
            api_key_input = input("   Paste your key here (or press Enter to skip): ").strip()
            if api_key_input:
                api_key = api_key_input
                print("✅ Using the Demo API key you entered")
            else:
                print("⚠️  No key provided — using public rate limit. "
                      "Get a free key at https://www.coingecko.com/en/developers/dashboard")

        if api_key:
            params['x_cg_demo_api_key'] = api_key

        headers = {'User-Agent': 'TopNonStableCoinsFetcher/2.0'}

        url = "https://api.coingecko.com/api/v3/coins/markets"
        print("📡 Fetching from CoinGecko...")
        response = self._make_request_with_retry(url, params, headers)

        data = response.json()

        filtered = []
        excluded = []
        skipped_stables = 0
        excluded_custom = 0

        for i, coin in enumerate(data, 1):
            coin_id = coin['id']
            price = coin.get('current_price') or 0
            symbol = coin.get('symbol', '').lower()
            name = coin.get('name', '').lower()

            if coin_id in self.STABLE_IDS:
                skipped_stables += 1
                excluded.append((i, coin, "Major stablecoin ID"))
                continue
            if coin_id in self.EXCLUDED_IDS:
                excluded_custom += 1
                excluded.append((i, coin, "Custom RWA/euro exclusion"))
                continue
            if 0.92 < price < 1.08 and ('usd' in symbol or 'usd' in name):
                skipped_stables += 1
                excluded.append((i, coin, "Dynamic USD-pegged stable"))
                continue

            filtered.append(coin)
            if len(filtered) >= limit:
                break

        print(f"✅ Fetched {len(data)} coins • "
              f"Skipped {skipped_stables} stablecoins • "
              f"Excluded {excluded_custom} custom coins • "
              f"Returning top {len(filtered)} non-stables\n")

        # Console preview
        print(f"{'Rank':<4} {'Name':<22} {'Symbol':<15} {'Price':>12} {'Market Cap':>18}")
        print("-" * 89)
        for rank, coin in enumerate(filtered[:5], 1):
            display_name = self._truncate_name(coin['name'])
            display_symbol = self._truncate_symbol(coin['symbol'].upper())
            print(f"{rank:<4} {display_name:<22} {display_symbol:<15} "
                  f"${coin['current_price']:>11,.4f}   ${coin['market_cap']:>15,.0f}")

        # Save both files
        self._save_main_list(filtered, skipped_stables, excluded_custom, limit)
        self._save_excluded_report(excluded, skipped_stables, excluded_custom, limit)

        return filtered

    def _save_main_list(self, filtered, skipped_stables, excluded_custom, limit):
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
        
        print(f"💾 Saved main list to: {filename}")

# ==================== COMMAND-LINE RUN ====================
if __name__ == "__main__":
    try:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    except (IndexError, ValueError):
        print("Usage: python get_gecko_top_coins.py [NUMBER]")
        limit = 100

    fetcher = TopNonStableCoinsFetcher()
    fetcher.fetch_and_save(limit)
