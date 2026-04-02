import requests
import pandas as pd
import time
import json
from typing import List, Dict

# ==================== CONFIG SECTION ====================
CONFIG = {
    'base_url': 'https://api.coingecko.com/api/v3',
    'vs_currency': 'usd',
    'order': 'market_cap_desc',
    'per_page': 250,                         # max allowed by API
    'pages': 1,                              # e.g. 1 = homepage view, 10 = top 2,500 tokens
    'locale': 'en',
    # Optional filters (set to None to disable)
    'category': None,                        # e.g. 'defi', 'meme-token', 'layer-1'
    'ids': None,                             # e.g. 'bitcoin,ethereum,solana'
    
    # ==================== OUTPUT FILENAMES ====================
    'output_csv': 'top_tokens_by_market_cap.csv',           # unfiltered version (original behavior)
    'output_filtered_csv': 'top_tokens_by_market_cap_filtered.csv',  # ← new file you requested
    'blacklist_file': 'blacklisted_tokens.json',            # path to your blacklist
}
# =======================================================

def fetch_coingecko_market_data(config: Dict = CONFIG) -> List[Dict]:
    """Fetch exactly like CoinGecko homepage — market-cap sorted."""
    all_coins: List[Dict] = []
    endpoint = f"{config['base_url']}/coins/markets"
    
    for page in range(1, config['pages'] + 1):
        params = {
            'vs_currency': config['vs_currency'],
            'order': config['order'],
            'per_page': config['per_page'],
            'page': page,
            'locale': config['locale']
        }
        
        if config.get('ids'):
            params['ids'] = config['ids']
        if config.get('category'):
            params['category'] = config['category']
            
        print(f"Fetching page {page}/{config['pages']}...")
        
        response = requests.get(endpoint, params=params)
        
        if response.status_code == 429:
            print("⚠️ Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            continue
        response.raise_for_status()
        
        data = response.json()
        all_coins.extend(data)
        
        if page < config['pages']:
            time.sleep(1.2)  # polite delay for free tier
    
    print(f"✅ Fetched {len(all_coins):,} tokens with official ranking.")
    return all_coins


def to_dataframe(coins: List[Dict]) -> pd.DataFrame:
    """Return ONLY the columns you requested, with nice names."""
    df = pd.DataFrame(coins)
    
    # Keep and rename exactly what you want
    df = df[[
        'market_cap_rank',
        'symbol',
        'id',
        'current_price',
        'total_volume',
        'market_cap'
    ]].copy()
    
    df = df.rename(columns={
        'market_cap_rank': 'ranking#',
        'current_price': 'price',
        'total_volume': '24h_volume',
        'market_cap': 'market_cap'
    })
    
    # Make numbers numeric (for easy sorting/filtering in Excel)
    numeric_cols = ['price', '24h_volume', 'market_cap']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Ensure it's still sorted by official rank
    df = df.sort_values('ranking#')
    
    return df


def load_blacklist(config: Dict = CONFIG) -> set:
    """Load blacklisted_tokens.json and return a set of IDs for fast lookup.
    
    Why IDs instead of symbols?
    - CoinGecko IDs are unique and stable.
    - Symbols can be duplicated or change over time.
    - Your JSON already provides clean 'id' fields (with a few nulls we safely ignore)."""
    try:
        with open(config['blacklist_file'], 'r', encoding='utf-8') as f:
            blacklist = json.load(f)
        
        # Only include entries that actually have an 'id'
        blacklisted_ids = {item.get('id') for item in blacklist if item.get('id')}
        
        print(f"✅ Loaded {len(blacklisted_ids):,} blacklisted tokens from {config['blacklist_file']}")
        return blacklisted_ids
    
    except FileNotFoundError:
        print(f"⚠️  Blacklist file '{config['blacklist_file']}' not found. No filtering will be applied.")
        return set()
    except json.JSONDecodeError:
        print(f"⚠️  Could not parse {config['blacklist_file']}. No filtering will be applied.")
        return set()


if __name__ == "__main__":
    # 1. Fetch fresh data from CoinGecko
    coins_data = fetch_coingecko_market_data()
    df = to_dataframe(coins_data)
    
    # 2. Load blacklist and create filtered version
    blacklisted_ids = load_blacklist()
    df_filtered = df[~df['id'].isin(blacklisted_ids)].copy()
    
    # 3. Report what happened (super useful for debugging / transparency)
    removed_count = len(df) - len(df_filtered)
    print(f"\n🔍 Filtering complete:")
    print(f"   • Original tokens : {len(df):,}")
    print(f"   • Blacklisted removed : {removed_count:,}")
    print(f"   • Remaining tokens  : {len(df_filtered):,}")
    
    # 4. Preview both versions
    print("\n=== Preview UNFILTERED (first 10 rows) ===")
    print(df.head(10).to_string(index=False))
    
    print(f"\n=== Preview FILTERED (first 10 rows) ===")
    print(df_filtered.head(10).to_string(index=False))
    
    # 5. Save both files (exactly the names from CONFIG)
    df.to_csv(CONFIG['output_csv'], index=False)
    df_filtered.to_csv(CONFIG['output_filtered_csv'], index=False)
    
    print(f"\n💾 Files saved:")
    print(f"   • {CONFIG['output_csv']}")
    print(f"   • {CONFIG['output_filtered_csv']}")
    
    print("\n✅ Done! Both CSVs are ready to open in Excel, Google Sheets, or load with pandas.")
