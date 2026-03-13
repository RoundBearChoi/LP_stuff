import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time
import sys

# ================== FETCH FUNCTIONS (unchanged) ==================
def fetch_klines(symbol: str, interval: str = '15m', days: int = 30):
    url = "https://fapi.binance.com/fapi/v1/klines"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    all_dfs = []
    current_start = start
    
    while True:
        params = {'symbol': symbol.upper(), 'interval': interval, 'limit': 1000}
        if current_start:
            params['startTime'] = int(current_start.timestamp() * 1000)
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
            
        cols = ['open_time', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'n', 'tbb', 'tbq', 'ignore']
        df = pd.DataFrame(data, columns=cols)
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        for c in ['open', 'high', 'low', 'close', 'volume']:
            df[c] = pd.to_numeric(df[c])
        
        df = df.set_index('open_time')
        all_dfs.append(df)
        
        if len(df) < 1000:
            break
            
        current_start = pd.to_datetime(df.index[-1]).tz_localize(None) + timedelta(milliseconds=10)
        time.sleep(0.2)
    
    return pd.concat(all_dfs).sort_index() if all_dfs else pd.DataFrame()

def fetch_open_interest(symbol: str, days: int = 30):
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    end = datetime.now(timezone.utc)
    all_dfs = []
    current_end = end
    max_loops = 20
    
    while len(all_dfs) < 5000 and max_loops > 0:
        params = {'symbol': symbol.upper(), 'period': '15m', 'limit': 500}
        params['endTime'] = int(current_end.timestamp() * 1000)
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data:
            break
            
        df = pd.DataFrame(data)
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['oi_value'] = pd.to_numeric(df['sumOpenInterestValue'])
        df = df.set_index('open_time')[['oi_value']]
        all_dfs.append(df)
        
        if len(df) < 500:
            break
            
        current_end = pd.to_datetime(df.index.min()).tz_localize(None) - timedelta(milliseconds=10)
        max_loops -= 1
        time.sleep(0.25)
    
    if all_dfs:
        full = pd.concat(all_dfs).drop_duplicates().sort_index()
        cutoff = (end - timedelta(days=days)).replace(tzinfo=None)
        return full[full.index >= cutoff]
    
    return pd.DataFrame()

# ================== MAIN ==================
if __name__ == "__main__":
    if len(sys.argv) == 1:
        sym1, sym2 = "BTC", "ETH"
        print("No arguments → using default BTC/ETH")
    elif len(sys.argv) == 3:
        sym1, sym2 = sys.argv[1].upper(), sys.argv[2].upper()
    else:
        print("Usage: python fetch_oi_standalone.py [SYMBOL1 SYMBOL2]")
        print("Example: python fetch_oi_standalone.py cake btc")
        sys.exit(1)

    print(f"Fetching fresh {sym1} & {sym2} price + Open Interest data (last 30 days)...")
    
    s1_price = fetch_klines(f'{sym1}USDT')
    s2_price = fetch_klines(f'{sym2}USDT')
    s1_oi = fetch_open_interest(f'{sym1}USDT')
    s2_oi = fetch_open_interest(f'{sym2}USDT')

    print("Merging into standalone dataset...")
    base = sym1.lower()
    quote = sym2.lower()
    
    combined = s1_price[['close']].rename(columns={'close': f'{base}_close'}) \
                .join(s2_price[['close']].rename(columns={'close': f'{quote}_close'}), how='inner') \
                .join(s1_oi.rename(columns={'oi_value': f'{base}_oi_value'}), how='left') \
                .join(s2_oi.rename(columns={'oi_value': f'{quote}_oi_value'}), how='left')

    combined[[f'{base}_oi_value', f'{quote}_oi_value']] = combined[[f'{base}_oi_value', f'{quote}_oi_value']].ffill()
    
    ratio_col = f'{base}_{quote}'
    combined[f'{ratio_col}_price_ratio'] = combined[f'{base}_close'] / combined[f'{quote}_close']
    combined[f'{ratio_col}_oi_ratio'] = combined[f'{base}_oi_value'] / combined[f'{quote}_oi_value']
    combined['oi_ratio_24h_change'] = combined[f'{ratio_col}_oi_ratio'].shift(-96) - combined[f'{ratio_col}_oi_ratio']
    combined['price_ratio_24h_change'] = combined[f'{ratio_col}_price_ratio'].shift(-96) - combined[f'{ratio_col}_price_ratio']

    csv_filename = f"{base}_{quote}_oi_standalone.csv"
    combined.to_csv(csv_filename)

    print(f"\n✅ SUCCESS! File created: {csv_filename}")
    print(f"   • Latest {sym1}/{sym2} OI Ratio (USD): {combined[f'{ratio_col}_oi_ratio'].iloc[-1]:.3f}")
    print(f"   • Total rows: {len(combined):,} (~30 days of 15m data)")
