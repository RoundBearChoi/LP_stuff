import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# ================== FETCH FUNCTIONS ==================
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
    start = end - timedelta(days=int(365.25 * years) + 3)  # +3 days buffer to catch first funding
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
    start = end - timedelta(days=int(365.25 * years) + 3)  # +3 days buffer
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

# ================== BTC-ETH COMBINED ==================
def create_btc_eth_combined(btc_merged: pd.DataFrame, eth_merged: pd.DataFrame):
    combined = btc_merged[['close', 'fundingRate']].rename(columns={'close':'btc_close', 'fundingRate':'btc_funding'}) \
                .join(
                    eth_merged[['close', 'fundingRate']].rename(columns={'close':'eth_close', 'fundingRate':'eth_funding'}), 
                    how='inner'
                )
    
    combined['btc_eth_ratio'] = combined['btc_close'] / combined['eth_close']
    combined['eth_btc_ratio'] = combined['eth_close'] / combined['btc_close']   # ← ADDED
    
    combined['funding_spread'] = combined['btc_funding'] - combined['eth_funding']
    
    # === CLEAN START: drop any rows before BOTH funding rates exist ===
    combined = combined.dropna(subset=['btc_funding', 'eth_funding']).copy()
    
    return combined

# ================== MAIN ==================
if __name__ == "__main__":
    INTERVAL = '15m'
    YEARS = 2
    
    print("Fetching ~2 years of BTC data... ⌛ pls wait")
    btc_price = get_full_klines('BTCUSDT', INTERVAL, YEARS)
    btc_fund  = get_full_funding_history('BTCUSDT', YEARS)
    
    print("Fetching ~2 years of ETH data... ⌛ pls wait")
    eth_price = get_full_klines('ETHUSDT', INTERVAL, YEARS)
    eth_fund  = get_full_funding_history('ETHUSDT', YEARS)
    
    print("Merging price + funding data...")
    btc_merged = merge_price_funding(btc_price, btc_fund)
    eth_merged = merge_price_funding(eth_price, eth_fund)
    
    print("Creating BTC/ETH combined dataset...")
    combined = create_btc_eth_combined(btc_merged, eth_merged)
    
    # ================== SAVE RAW DATA ==================
    btc_merged.to_csv("btc_merged_2y.csv")
    eth_merged.to_csv("eth_merged_2y.csv")
    combined.to_csv("btc_eth_funding_spread_2y.csv")
    
    print(f"\n✅ All raw data saved!")
    print(f"   • BTC full:   btc_merged_2y.csv          ({len(btc_merged):,} rows)")
    print(f"   • ETH full:   eth_merged_2y.csv          ({len(eth_merged):,} rows)")
    print(f"   • Combined:   btc_eth_funding_spread_2y.csv ({len(combined):,} rows)")
    
    print(f"\n📅 Actual clean data range:")
    print(f"   From: {combined.index[0]}")
    print(f"   To:   {combined.index[-1]}")
    print(f"\nFiles are ready in your current folder. Now includes both btc_eth_ratio and eth_btc_ratio! 🎯")
