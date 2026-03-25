import pandas as pd
import requests
import time
import os
import matplotlib.pyplot as plt
import numpy as np

# ====================== CONFIG (change these!) ======================
PERCENTILE = 90          # ←←← CHANGE THIS TO WHATEVER YOU WANT
                         # Examples: 70, 80, 90, 95, 99, 99.9

MIN_VOLUME_RATIO = 0.20  # ←←← NEW: Minimum ratio of smaller volume / larger volume
                         # Filter out pairs where one symbol's volume < 30% of the other
                         # Examples: 0.25, 0.30, 0.40, 0.50
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


# ====================== MAIN ======================
if __name__ == "__main__":
    input_file = "filtered_by_stability_johansen_one_direction_18m_top42778.csv"
    output_file = input_file.replace("stability", "volume")
    
    if not os.path.exists(input_file):
        print(f"❌ Original file '{input_file}' not found!")
        exit(1)
    
    # Smart check: reuse existing file if you just want a chart refresh
    skip_fetch = False
    if os.path.exists(output_file):
        print(f"✅ Existing volume file found: {output_file}")
        response = input("Do you want to skip fetching new volume data from MEXC and KuCoin "
                         "and only regenerate the sorted rank chart? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            print("📊 Loading existing volume file (skipping API calls)...")
            df = pd.read_csv(output_file)
            skip_fetch = True
        else:
            print("🔄 Proceeding with full volume refresh...")
    else:
        print("📊 No existing volume file found. Running full process...")
    
    # Full process only if needed
    if not skip_fetch:
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
        
        symbols = pd.concat([df['symbol1'], df['symbol2']]).unique()
        print(f"🔍 Found {len(symbols):,} unique symbols. Fetching MEXC + KuCoin 7d volumes...")
        volume_cache = {}
        for i, sym in enumerate(symbols, 1):
            if i % 25 == 0 or i == len(symbols):
                print(f"   Progress: {i}/{len(symbols)} symbols")
            mexc_vol = get_mexc_7d_avg_volume(sym)
            kucoin_vol = get_kucoin_7d_avg_volume(sym)
            volume_cache[sym] = {'mexc': mexc_vol, 'kucoin': kucoin_vol}
            time.sleep(0.25)
        
        print("➕ Adding volume columns...")
        df['mexc_symbol1_7d_avg_vol_usdt'] = df['symbol1'].map(lambda x: volume_cache.get(x, {}).get('mexc', 0.0))
        df['mexc_symbol2_7d_avg_vol_usdt'] = df['symbol2'].map(lambda x: volume_cache.get(x, {}).get('mexc', 0.0))
        df['kucoin_symbol1_7d_avg_vol_usdt'] = df['symbol1'].map(lambda x: volume_cache.get(x, {}).get('kucoin', 0.0))
        df['kucoin_symbol2_7d_avg_vol_usdt'] = df['symbol2'].map(lambda x: volume_cache.get(x, {}).get('kucoin', 0.0))
        
        print("📊 Calculating total volumes...")
        df['symbol1_total_7d_vol_usdt'] = df['mexc_symbol1_7d_avg_vol_usdt'] + df['kucoin_symbol1_7d_avg_vol_usdt']
        df['symbol2_total_7d_vol_usdt'] = df['mexc_symbol2_7d_avg_vol_usdt'] + df['kucoin_symbol2_7d_avg_vol_usdt']
        df['pair_total_7d_vol_usdt'] = df['symbol1_total_7d_vol_usdt'] + df['symbol2_total_7d_vol_usdt']
    
    # ====================== ALWAYS RUN: VOLUME BALANCE FILTER ======================
    print(f"🔍 Applying volume balance filter ({MIN_VOLUME_RATIO*100:.0f}% min ratio)...")
    before_balance = len(df)
    
    v_cols = ['symbol1_total_7d_vol_usdt', 'symbol2_total_7d_vol_usdt']
    # Vectorized: keep only pairs where min >= ratio * max AND both volumes > 0
    mask = (
        (df[v_cols] > 0).all(axis=1) &
        (df[v_cols].min(axis=1) >= MIN_VOLUME_RATIO * df[v_cols].max(axis=1))
    )
    
    df = df[mask].copy().reset_index(drop=True)
    print(f"   Kept {len(df):,} balanced pairs | Discarded {before_balance - len(df):,} imbalanced pairs")
    # ===========================================================================

    # ====================== ALWAYS RUN: SORT + PERCENTILES + CHART + SAVE ======================
    print("🔄 Sorting pairs from highest total volume to lowest...")
    df = df.sort_values(by='pair_total_7d_vol_usdt', ascending=False).reset_index(drop=True)
    
    print("📊 Calculating volume percentile ranks...")
    df['volume_percentile'] = (df['pair_total_7d_vol_usdt'].rank(pct=True) * 100).round(2)
    
    df['volume_percentile_rank'] = df['volume_percentile'].round(0).astype(int).map(ordinal) + " percentile"
    
    # Move new columns right after total volume
    cols = list(df.columns)
    try:
        total_idx = cols.index('pair_total_7d_vol_usdt')
        for col in ['volume_percentile_rank', 'volume_percentile'][::-1]:
            cols.insert(total_idx + 1, cols.pop(cols.index(col)))
        df = df[cols]
    except:
        pass
    
    volumes = df['pair_total_7d_vol_usdt']
    percentile_fraction = PERCENTILE / 100.0
    p_value = volumes.quantile(percentile_fraction)
    print(f"📈 {PERCENTILE}th percentile total volume: ${p_value:,.0f} USDT")
    print(f"   Top pair is at {df['volume_percentile_rank'].iloc[0]}")
    
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
    
    # Save (or re-save) the CSV
    df.to_csv(output_file, index=False)
    print(f"\n✅ DONE! Final file: {output_file} ({len(df):,} rows)")
    print(f"   Filters applied: Strong Cointegration + Non-Noise + {MIN_VOLUME_RATIO*100:.0f}% Volume Balance")
    print(f"   New columns added: volume_percentile + volume_percentile_rank")
    print(f"   Chart: {chart_file}")
    if skip_fetch:
        print("   (Used existing volume data — no new API calls)")
