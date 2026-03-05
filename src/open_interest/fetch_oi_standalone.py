import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# ================== FETCH FUNCTIONS (FINAL ROBUST VERSION) ==================
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
    max_loops = 20  # safety
    
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
        # Make cutoff tz-naive to match pandas index
        cutoff = (end - timedelta(days=days)).replace(tzinfo=None)
        return full[full.index >= cutoff]
    
    return pd.DataFrame()

# ================== MAIN ==================
if __name__ == "__main__":
    print("Fetching fresh BTC & ETH price + Open Interest data (last 30 days)...")
    btc_price = fetch_klines('BTCUSDT')
    eth_price = fetch_klines('ETHUSDT')
    btc_oi = fetch_open_interest('BTCUSDT')
    eth_oi = fetch_open_interest('ETHUSDT')

    print("Merging into standalone dataset...")
    combined = btc_price[['close']].rename(columns={'close': 'btc_close'}) \
                .join(eth_price[['close']].rename(columns={'close': 'eth_close'}), how='inner') \
                .join(btc_oi.rename(columns={'oi_value': 'btc_oi_value'}), how='left') \
                .join(eth_oi.rename(columns={'oi_value': 'eth_oi_value'}), how='left')

    combined[['btc_oi_value', 'eth_oi_value']] = combined[['btc_oi_value', 'eth_oi_value']].ffill()
    
    combined['btc_eth_price_ratio'] = combined['btc_close'] / combined['eth_close']
    combined['btc_eth_oi_ratio'] = combined['btc_oi_value'] / combined['eth_oi_value']
    combined['oi_ratio_24h_change'] = combined['btc_eth_oi_ratio'].shift(-96) - combined['btc_eth_oi_ratio']
    combined['price_ratio_24h_change'] = combined['btc_eth_price_ratio'].shift(-96) - combined['btc_eth_price_ratio']

    combined.to_csv("btc_eth_oi_standalone.csv")

    print(f"\n✅ SUCCESS! File created: btc_eth_oi_standalone.csv")
    print(f"   • Latest BTC/ETH OI Ratio (USD): {combined['btc_eth_oi_ratio'].iloc[-1]:.3f}")
    print(f"   • Total rows: {len(combined):,} (~30 days of 15m data)")
