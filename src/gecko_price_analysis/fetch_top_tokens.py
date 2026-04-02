import requests
import pandas as pd
import time
from typing import List, Dict

# ==================== CONFIG SECTION ====================
# Customize everything here — no other code changes needed
CONFIG = {
    'base_url': 'https://api.coingecko.com/api/v3',
    'vs_currency': 'usd',                    # change to 'eur', 'btc', 'krw', etc.
    'order': 'market_cap_desc',              # market_cap_desc is what the homepage uses
    'per_page': 250,                         # max allowed by API
    'pages': 1,                              # e.g. 1 = homepage view, 10 = top 2,500 tokens
    'locale': 'en',
    # Optional filters (set to None to disable)
    'category': None,                        # e.g. 'defi', 'meme-token', 'layer-1'
    'ids': None,                             # e.g. 'bitcoin,ethereum,solana'
    
    # ==================== OUTPUT FILENAMES ====================
    'output_csv': 'top_tokens_by_market_cap.csv',   # ← exactly what you wanted
    # If you ever want timestamped files again, uncomment the next two lines and comment the one above:
    # timestamp = time.strftime("%Y%m%d_%H%M%S")
    # 'output_csv': f'top_tokens_by_market_cap_{timestamp}.csv',
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


if __name__ == "__main__":
    coins_data = fetch_coingecko_market_data()
    df = to_dataframe(coins_data)
    
    print("\n=== Preview (first 10 rows) ===")
    print(df.head(10).to_string(index=False))
    
    # Save with the exact filename from CONFIG
    df.to_csv(CONFIG['output_csv'], index=False)
    print(f"\n💾 CSV saved as: {CONFIG['output_csv']}")
    
    print("\n✅ Done! Your file is ready to open in Excel, Google Sheets, or load with pandas.")
