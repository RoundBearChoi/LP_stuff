import requests
from datetime import datetime
import sys
import unicodedata
import time
import os

class TopNonStableCoinsFetcher:
    BLACKLISTED_IDS = {
        'a7a5',
        'adi-token',
        'affine',
        'alphabet-class-a-ondo-tokenized-stock',
        'america',
        'anchored-coins-eur',
        'apenft',
        'apollo-diversified-credit-securitize-fund',
        'atomone',
        'atoshi',
        'aztec',
        'babyboomtoken',
        'basedhype',
        'bianrensheng',
        'bim',
        'bitdca',
        'bitlayer',
        'bittorrent',
        'bitway',
        'blockchain-capital',
        'bnb48-club-token',
        'bold-2',
        'botxcoin',
        'brz',
        'burnedfi',
        'cash-4',
        'changenow',
        'chutes',
        'circle-internet-group-ondo-tokenized-stock',
        'coincollect',
        'collect-on-fanable',
        'conscious-token',
        'crown-brlv',
        'dacxi',
        'dai',
        'xdai',
        'diem',
        'dola-usd',
        'ethena-usde',
        'eur-coinvertible',
        'euro-coin',
        'eutbl',
        'exod',
        'fidelity-digital-dollar',
        'fidelity-digital-interest-token',
        'figure-heloc',
        'first-digital-usd',
        'flying-tulip',
        'frax',
        'fx-usd-saving',
        'gama-token',
        'gamer-tag',
        'gho',
        'glidr',
        'gmt-token',
        'grx-chain',
        'hash-2',                                           # Provenance Blockchain (HASH)
        'hashnote-usyc',
        'hastra-prime',
        'helder',
        'hippius',
        'infinifi-locked-iusd-1week',
        'ini',
        'iota',
        'iota-2',
        'ium',
        'janus-henderson-anemoy-aaa-clo-fund',
        'janus-henderson-anemoy-treasury-fund',
        'just',
        'kelp-gain',
        'kinesis-gold',
        'kinetiq',
        'liquity-bold-2',
        'lium',
        'luxxcoin',
        'mag7-ssi',
        'mai',
        'main-street-yield',
        'mantle',
        'mantra',
        'mbg-by-multibank-group',
        'meta-2-2',
        'micron-technology-ondo-tokenized-stock',
        'midas-mf-one',
        'midas-mhyper',
        'midas-mtbill',
        'mindwavedao',
        'monerium-eur-money',
        'monerium-eur-money-2',
        'nest-basis-vault',
        'nirvana-ana-2',
        'nkyc-token',
        'noon-usn',
        'official-trump',
        'ondo-us-dollar-yield',
        'onyc',
        'ousg',
        'palladium-network',
        'pax-gold',
        'paypal-usd',
        'pleasing-gold',
        'polymtrade',
        'proprietary-trading-network',
        'rain',
        'ravedao',
        'resolv-rlp',
        'resolv-usr',
        'ridges-ai',
        'ripple',
        'robo-token-2',
        'rollbit-coin',
        'ronin',
        'ryze',
        'score',
        'securitize-tokenized-aaa-clo-fund',
        'sentient',
        'shuffle-2',
        'singularry',
        'snowbank',
        'societe-generale-forge',
        'spdr-s-p-500-etf-ondo-tokenized-etf',
        'spiko-us-t-bills-money-market-fund',
        'stasis-eurs',
        'stronghold',
        'sun-token',
        'superstate-short-duration-us-government-securities-fund-ustb',
        'sygnum-fiusd-liquidity-fund',
        'targon',
        'tcy',
        'tdccp',
        'templar',
        'temple',
        'tesla-xstock',
        'tether',
        'tether-gold',
        'the-grays-currency',
        'the9bit',
        'theo-short-duration-us-treasury-fund',
        'thetrumptoken',
        'tradable-na-rent-financing-platform-sstn',
        'tradable-singapore-fintech-ssl-2',
        'tria',
        'tron',
        'tronbank',
        'true-usd',
        'tx',
        'unit-plasma',
        'unit-pump',
        'unitywallet-token',
        'usd',
        'usd-coin',
        'usdd',
        'usds',
        'usdx',
        'ustbl',
        'usx',
        'vaneck-treasury-fund',
        'verified-emeralds',
        'war-2',
        'wojak-finance',
        'would',
        'yearn-finance',
        'ylds'
    }

    # Tiny helper for nice reporting only (former major stables)
    KNOWN_STABLES = {
        'tether', 'usd-coin', 'usds', 'ethena-usde', 'dai',
        'paypal-usd', 'first-digital-usd', 'true-usd', 'usdd', 'frax'
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
            f.write(f"Total custom excluded: {excluded_custom}\n")
            f.write(f"Total blacklisted: {len(excluded)}\n\n")

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

        headers = {'User-Agent': 'TopNonStableCoinsFetcher/2.0'}
        url = "https://api.coingecko.com/api/v3/coins/markets"

        # === PAGINATION LOGIC – GUARANTEES EXACTLY `limit` NON-STABLECOINS ===
        filtered = []
        excluded = []
        skipped_stables = 0
        excluded_custom = 0
        page = 1
        global_rank = 0
        max_pages = 8  # safety cap (2000 coins max)

        print("📡 Fetching from CoinGecko...")

        while len(filtered) < limit and page <= max_pages:
            params = {
                'vs_currency': self.vs_currency.lower(),
                'order': 'market_cap_desc',
                'per_page': 250,
                'page': page,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            if api_key:
                params['x_cg_demo_api_key'] = api_key

            response = self._make_request_with_retry(url, params, headers)
            data = response.json()

            if not data:
                print("   No more data from CoinGecko")
                break

            for coin in data:
                global_rank += 1
                coin_id = coin['id']
                price = coin.get('current_price') or 0
                symbol = coin.get('symbol', '').lower()
                name = coin.get('name', '').lower()

                # === SINGLE GIANT BLACKLIST CHECK ===
                if coin_id in self.BLACKLISTED_IDS:
                    reason = "Stablecoin" if coin_id in self.KNOWN_STABLES else "Blacklisted"
                    if coin_id in self.KNOWN_STABLES:
                        skipped_stables += 1
                    else:
                        excluded_custom += 1
                    excluded.append((global_rank, coin, reason))
                    continue

                # Dynamic USD-pegged stable (catches new ones not yet blacklisted)
                if 0.92 < price < 1.08 and ('usd' in symbol or 'usd' in name):
                    skipped_stables += 1
                    excluded.append((global_rank, coin, "Dynamic USD-pegged stable"))
                    continue

                filtered.append(coin)
                if len(filtered) >= limit:
                    break

            print(f"   Page {page} → {len(filtered)}/{limit} non-stables collected so far")
            page += 1

        print(f"✅ Fetched {global_rank} raw coins across {page-1} page(s) • "
              f"Blacklisted {skipped_stables + excluded_custom} coins • "
              f"Returning exactly {len(filtered)} non-stables\n")

        # Console preview (unchanged)
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
            f.write(f"Blacklisted stablecoins: {skipped_stables}\n")
            f.write(f"Blacklisted custom coins: {excluded_custom}\n")
            f.write(f"Total blacklisted: {skipped_stables + excluded_custom}\n\n")
            
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
        limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    except (IndexError, ValueError):
        print("Usage: python get_gecko_top_coins.py [NUMBER]")
        limit = 200

    fetcher = TopNonStableCoinsFetcher()
    fetcher.fetch_and_save(limit)
