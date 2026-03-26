import pandas as pd
import requests
import time
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# ====================== CONFIG (change these!) ======================
PERCENTILE = 50
MIN_VOLUME_RATIO = 0.30
VOLUME_CACHE_FILE = "mexc_kucoin_volume.csv" 
# ===========================================================================

def ordinal(n: int) -> str:
    """Proper English suffixes: 1st, 2nd, 3rd, 4th..."""
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"

def get_mexc_7d_avg_volume(symbol):
    if pd.isna(symbol) or str(symbol).strip() == '':
        return 0.0
    pair = f"{str(symbol).strip().upper()}USDT"
    try:
        url = "https://api.mexc.com/api/v3/klines"
        params = {'symbol': pair, 'interval': '1d', 'limit': 10}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return 0.0
        data = resp.json()
        if not isinstance(data, list) or len(data) < 7:
            return 0.0
        quote_volumes = [float(candle[7]) for candle in data[-8:-1] if len(candle) > 7]
        return sum(quote_volumes) / len(quote_volumes) if quote_volumes else 0.0
    except Exception:
        return 0.0


def get_kucoin_7d_avg_volume(symbol):
    if pd.isna(symbol) or str(symbol).strip() == '':
        return 0.0
    pair = f"{str(symbol).strip().upper()}-USDT"
    try:
        url = "https://api.kucoin.com/api/v1/market/candles"
        now = int(time.time())
        start_at = now - 10 * 24 * 3600
        params = {'symbol': pair, 'type': '1day', 'startAt': start_at, 'endAt': now}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return 0.0
        result = resp.json()
        if result.get('code') != '200000' or not result.get('data'):
            return 0.0
        candles = result['data']
        if len(candles) < 7:
            return 0.0
        quote_volumes = [float(candle[6]) for candle in candles[:7]]
        return sum(quote_volumes) / len(quote_volumes) if quote_volumes else 0.0
    except Exception:
        return 0.0


def load_volume_cache():
    if os.path.exists(VOLUME_CACHE_FILE):
        df_cache = pd.read_csv(VOLUME_CACHE_FILE)
        print(f"✅ Loaded existing volume cache with {len(df_cache):,} symbols")
        return df_cache
    else:
        print(f"📂 No volume cache found → will create {VOLUME_CACHE_FILE}")
        return pd.DataFrame(columns=['symbol', 'mexc_7d_avg_vol_usdt', 'kucoin_7d_avg_vol_usdt', 'last_updated'])


def save_volume_cache(df_cache):
    df_cache.to_csv(VOLUME_CACHE_FILE, index=False)
    print(f"💾 Saved/updated volume cache → {VOLUME_CACHE_FILE} ({len(df_cache):,} symbols)")


# ====================== MAIN ======================
if __name__ == "__main__":
    input_file = "filtered_by_stability_johansen_one_direction_18m_top42778.csv"
    output_file = input_file.replace("stability", "volume")
    
    if not os.path.exists(input_file):
        print(f"❌ Original file '{input_file}' not found!")
        exit(1)
    
    # Load original stability results
    print("📊 Loading original CSV...")
    df = pd.read_csv(input_file)
    original_rows = len(df)
    print(f"   Loaded {original_rows:,} rows")
    
    print("🔍 Applying strict filters (noise=False + STRONG COINTEGRATION)...")
    df = df[
        (df['noise'] == False) & 
        (df['verdict'].astype(str).str.contains('STRONG COINTEGRATION', case=False, na=False))
    ].copy()
    print(f"   Kept {len(df):,} high-quality pairs | Discarded {original_rows - len(df):,} rows")
    
    # Unique symbols
    symbols = pd.concat([df['symbol1'], df['symbol2']]).unique()
    print(f"🔍 Found {len(symbols):,} unique symbols")
    
    # Load volume cache
    volume_cache_df = load_volume_cache()
    cached_symbols = set(volume_cache_df['symbol'].astype(str).str.upper())
    
    # Find symbols we still need to fetch
    missing_symbols = [str(s).strip().upper() for s in symbols 
                       if str(s).strip().upper() not in cached_symbols]
    
    # ====================== PROMPT LOGIC (exactly as you asked) ======================
    force_refresh = False
    if missing_symbols:
        print(f"🔄 Fetching volume data for {len(missing_symbols):,} NEW symbols...")
    else:
        print("✅ All symbols already present in volume cache")
        response = input("Do you want to skip fetching fresh volume data from MEXC and KuCoin "
                         "and only use the cached data? (y/n): ").strip().lower()
        if response in ['n', 'no']:
            print("🔄 Forcing full volume refresh for all symbols...")
            force_refresh = True
            missing_symbols = [str(s).strip().upper() for s in symbols]
        else:
            print("📊 Using existing volume cache (no API calls)...")
    
    # Fetch (either new symbols or full refresh if user chose n)
    if missing_symbols:
        new_rows = []
        for i, sym in enumerate(missing_symbols, 1):
            if i % 20 == 0 or i == len(missing_symbols):
                print(f"   Progress: {i}/{len(missing_symbols)} symbols")
            mexc_vol = get_mexc_7d_avg_volume(sym)
            kucoin_vol = get_kucoin_7d_avg_volume(sym)
            new_rows.append({
                'symbol': sym,
                'mexc_7d_avg_vol_usdt': mexc_vol,
                'kucoin_7d_avg_vol_usdt': kucoin_vol,
                'last_updated': datetime.now().isoformat()
            })
            time.sleep(0.25)
        
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            volume_cache_df = pd.concat([volume_cache_df, new_df], ignore_index=True)
            volume_cache_df = volume_cache_df.drop_duplicates(subset=['symbol']).reset_index(drop=True)
            save_volume_cache(volume_cache_df)
    # ================================================================================
    
    # Build fast lookup dictionary
    volume_dict = {}
    for _, row in volume_cache_df.iterrows():
        sym = str(row['symbol']).upper()
        volume_dict[sym] = {
            'mexc': float(row['mexc_7d_avg_vol_usdt']),
            'kucoin': float(row['kucoin_7d_avg_vol_usdt'])
        }
    
    # Add volumes to pairs
    print("➕ Adding volume columns from cache...")
    df['mexc_symbol1_7d_avg_vol_usdt'] = df['symbol1'].map(lambda x: volume_dict.get(str(x).upper(), {}).get('mexc', 0.0))
    df['mexc_symbol2_7d_avg_vol_usdt'] = df['symbol2'].map(lambda x: volume_dict.get(str(x).upper(), {}).get('mexc', 0.0))
    df['kucoin_symbol1_7d_avg_vol_usdt'] = df['symbol1'].map(lambda x: volume_dict.get(str(x).upper(), {}).get('kucoin', 0.0))
    df['kucoin_symbol2_7d_avg_vol_usdt'] = df['symbol2'].map(lambda x: volume_dict.get(str(x).upper(), {}).get('kucoin', 0.0))
    
    print("📊 Calculating total volumes...")
    df['symbol1_total_7d_vol_usdt'] = df['mexc_symbol1_7d_avg_vol_usdt'] + df['kucoin_symbol1_7d_avg_vol_usdt']
    df['symbol2_total_7d_vol_usdt'] = df['mexc_symbol2_7d_avg_vol_usdt'] + df['kucoin_symbol2_7d_avg_vol_usdt']
    df['pair_total_7d_vol_usdt'] = df['symbol1_total_7d_vol_usdt'] + df['symbol2_total_7d_vol_usdt']
    
    # Volume balance filter
    print(f"🔍 Applying volume balance filter ({MIN_VOLUME_RATIO*100:.0f}% min ratio)...")
    before_balance = len(df)
    v_cols = ['symbol1_total_7d_vol_usdt', 'symbol2_total_7d_vol_usdt']
    mask = (
        (df[v_cols] > 0).all(axis=1) &
        (df[v_cols].min(axis=1) >= MIN_VOLUME_RATIO * df[v_cols].max(axis=1))
    )
    df = df[mask].copy().reset_index(drop=True)
    print(f"   Kept {len(df):,} balanced pairs | Discarded {before_balance - len(df):,} imbalanced pairs")
    
    # Sort + percentiles + chart + save
    print("🔄 Sorting pairs from highest total volume to lowest...")
    df = df.sort_values(by='pair_total_7d_vol_usdt', ascending=False).reset_index(drop=True)
    
    print("📊 Calculating volume percentile ranks...")
    df['volume_percentile'] = (df['pair_total_7d_vol_usdt'].rank(pct=True) * 100).round(2)
    df['volume_percentile_rank'] = df['volume_percentile'].round(0).astype(int).map(ordinal) + " percentile"
    
    # Reorder columns for readability
    cols = list(df.columns)
    try:
        total_idx = cols.index('pair_total_7d_vol_usdt')
        for col in ['volume_percentile_rank', 'volume_percentile'][::-1]:
            if col in cols:
                cols.insert(total_idx + 1, cols.pop(cols.index(col)))
        df = df[cols]
    except:
        pass
    
    volumes = df['pair_total_7d_vol_usdt']
    p_value = volumes.quantile(PERCENTILE / 100.0)
    print(f"📈 {PERCENTILE}th percentile total volume: ${p_value:,.0f} USDT")
    
    print(f"📈 Generating sorted rank chart ({PERCENTILE}th percentile, {MIN_VOLUME_RATIO*100:.0f}% balanced, log scale)...")
    plt.figure(figsize=(14, 8), dpi=150)
    ranks = range(1, len(df) + 1)
    plot_volumes = np.maximum(volumes, 1)
    plt.plot(ranks, plot_volumes, linewidth=2, color='#3498db')
    plt.axhline(p_value, color='red', linestyle='--', linewidth=2.5, 
                label=f'{PERCENTILE}th Percentile (${p_value:,.0f} USDT)')
    plt.yscale('log')
    
    plt.title(f'Pair Total 7-Day Volume - Sorted Highest to Lowest Rank\n'
              f'Strong Cointegration + Non-Noise + {MIN_VOLUME_RATIO*100:.0f}% Volume Balanced Pairs '
              f'({PERCENTILE}th Percentile Marked)', 
              fontsize=14, pad=20)
    plt.xlabel('Pair Rank (1 = Highest Total Volume)')
    plt.ylabel('Pair Total Volume USDT (log scale)')
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    
    chart_file = "pair_total_volume_sorted_rank.png"
    plt.savefig(chart_file, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"   ✅ Chart saved → {chart_file}")
    
    # Save the final filtered/ranked results
    df.to_csv(output_file, index=False)
    print(f"\n✅ DONE!")
    print(f"   Final filtered pairs file → {output_file} ({len(df):,} rows)")
    print(f"   Separate volume cache      → {VOLUME_CACHE_FILE} ({len(volume_cache_df):,} symbols)")
    print(f"   Filters applied: Strong Cointegration + Non-Noise + {MIN_VOLUME_RATIO*100:.0f}% Volume Balance")
