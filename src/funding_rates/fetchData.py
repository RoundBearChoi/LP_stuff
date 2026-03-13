import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import sys

# ================== FETCH FUNCTIONS (unchanged) ==================
def fetch_funding_rates(symbol: str, start_time=None, end_time=None, limit: int = 1000):
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {'symbol': symbol.upper(), 'limit': limit}
    if start_time:
        params['startTime'] = int(start_time.timestamp() * 1000)
    if end_time:
        params['endTime'] = int(end_time.timestamp() * 1000)
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    if not data:
        return pd.DataFrame(columns=['fundingTime', 'fundingRate'])
    
    df = pd.DataFrame(data)
    df['fundingTime'] = pd.to_datetime(df['fundingTime'], unit='ms')
    df['fundingRate'] = pd.to_numeric(df['fundingRate'])
    return df[['fundingTime', 'fundingRate']]

def get_full_funding_history(symbol: str, years: int = 2):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(365.25 * years) + 3)
    all_dfs = []
    current_start = start
    
    while True:
        df = fetch_funding_rates(symbol, current_start, end, limit=1000)
        if df.empty or len(df) == 0:
            break
        all_dfs.append(df)
        if len(df) < 1000:
            break
        current_start = df['fundingTime'].iloc[-1] + timedelta(milliseconds=10)
        time.sleep(0.2)
    
    if not all_dfs:
        return pd.DataFrame()
    
    full = pd.concat(all_dfs).drop_duplicates(subset=['fundingTime']).sort_values('fundingTime').reset_index(drop=True)
    return full

def fetch_klines(symbol: str, interval: str = '15m', start_time=None, end_time=None, limit: int = 1000):
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {'symbol': symbol.upper(), 'interval': interval, 'limit': limit}
    if start_time:
        params['startTime'] = int(start_time.timestamp() * 1000)
    if end_time:
        params['endTime'] = int(end_time.timestamp() * 1000)
    
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    
    if not data:
        return pd.DataFrame()
    
    cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'n', 'tbb', 'tbq', 'ignore']
    df = pd.DataFrame(data, columns=cols)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = pd.to_numeric(df[c])
    return df.set_index('open_time')

def get_full_klines(symbol: str, interval: str = '15m', years: int = 2):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(365.25 * years) + 3)
    all_dfs = []
    current_start = start
    
    while True:
        df = fetch_klines(symbol, interval, current_start, end, limit=1000)
        if df.empty or len(df) == 0:
            break
        all_dfs.append(df)
        if len(df) < 1000:
            break
        current_start = df.index[-1] + timedelta(milliseconds=10)
        time.sleep(0.2)
    
    if not all_dfs:
        return pd.DataFrame()
    
    full = pd.concat(all_dfs).drop_duplicates().sort_index()
    return full

def merge_price_funding(price_df: pd.DataFrame, funding_df: pd.DataFrame) -> pd.DataFrame:
    funding = funding_df.set_index('fundingTime')
    combined = price_df.join(funding['fundingRate'], how='left')
    combined['fundingRate'] = combined['fundingRate'].ffill()
    return combined

# ================== GENERALIZED COMBINED ==================
def create_pair_combined(merged1: pd.DataFrame, merged2: pd.DataFrame, sym1: str, sym2: str):
    s1 = sym1.lower()
    s2 = sym2.lower()
    combined = merged1[['close', 'fundingRate']].rename(columns={
                'close': f'{s1}_close', 
                'fundingRate': f'{s1}_funding'
            }).join(
                merged2[['close', 'fundingRate']].rename(columns={
                    'close': f'{s2}_close', 
                    'fundingRate': f'{s2}_funding'
                }), how='inner'
            )
    
    combined[f'{s1}_{s2}_ratio'] = combined[f'{s1}_close'] / combined[f'{s2}_close']
    combined[f'{s2}_{s1}_ratio'] = combined[f'{s2}_close'] / combined[f'{s1}_close']
    
    combined['funding_spread'] = combined[f'{s1}_funding'] - combined[f'{s2}_funding']
    
    combined = combined.dropna(subset=[f'{s1}_funding', f'{s2}_funding']).copy()
    return combined

# ================== MAIN ==================
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python fetchData.py <symbol1> <symbol2>")
        print("Example: python fetchData.py cake btc")
        sys.exit(1)

    sym1 = sys.argv[1].upper()
    sym2 = sys.argv[2].upper()
    s1 = sym1.lower()
    s2 = sym2.lower()

    INTERVAL = '15m'
    YEARS = 2
    
    print(f"Fetching ~2 years of {sym1} data... ⌛ pls wait")
    price1 = get_full_klines(f'{sym1}USDT', INTERVAL, YEARS)
    fund1  = get_full_funding_history(f'{sym1}USDT', YEARS)
    
    print(f"Fetching ~2 years of {sym2} data... ⌛ pls wait")
    price2 = get_full_klines(f'{sym2}USDT', INTERVAL, YEARS)
    fund2  = get_full_funding_history(f'{sym2}USDT', YEARS)
    
    print("Merging price + funding data...")
    merged1 = merge_price_funding(price1, fund1)
    merged2 = merge_price_funding(price2, fund2)
    
    print(f"Creating {sym1}/{sym2} combined dataset...")
    combined = create_pair_combined(merged1, merged2, sym1, sym2)
    
    merged1.to_csv(f"{s1}_merged_2y.csv")
    merged2.to_csv(f"{s2}_merged_2y.csv")
    combined.to_csv(f"{s1}_{s2}_funding_spread_2y.csv")
    
    print(f"\n✅ All raw data saved for {sym1}-{sym2}!")
    print(f"   • {sym1}: {s1}_merged_2y.csv          ({len(merged1):,} rows)")
    print(f"   • {sym2}: {s2}_merged_2y.csv          ({len(merged2):,} rows)")
    print(f"   • Combined: {s1}_{s2}_funding_spread_2y.csv ({len(combined):,} rows)")
    
    print(f"\n📅 Actual clean data range:")
    print(f"   From: {combined.index[0]}")
    print(f"   To:   {combined.index[-1]}")
    print(f"\nFiles are ready! Includes both {s1}_{s2}_ratio and {s2}_{s1}_ratio. 🎯")
