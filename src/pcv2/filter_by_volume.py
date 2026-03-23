import pandas as pd
import requests
import time
import os
import matplotlib.pyplot as plt
import numpy as np

# ====================== CONFIG (change this one line!) ======================
PERCENTILE = 90          # ←←← CHANGE THIS TO WHATEVER YOU WANT
                         # Examples: 70, 80, 90, 95, 99, 99.9
                         # The script will automatically mark this percentile
                         # on the chart and update all titles/labels
# ===========================================================================

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
    
    # Always run: sort + chart + save
    print("🔄 Sorting pairs from highest total volume to lowest...")
    df = df.sort_values(by='pair_total_7d_vol_usdt', ascending=False).reset_index(drop=True)
    
    volumes = df['pair_total_7d_vol_usdt']
    percentile_fraction = PERCENTILE / 100.0
    p_value = volumes.quantile(percentile_fraction)
    print(f"📈 {PERCENTILE}th percentile total volume: ${p_value:,.0f} USDT")
    
    print(f"📈 Generating sorted rank chart ({PERCENTILE}th percentile, log scale)...")
    plt.figure(figsize=(14, 8), dpi=150)
    ranks = range(1, len(df) + 1)
    plot_volumes = np.maximum(volumes, 1)
    plt.plot(ranks, plot_volumes, linewidth=2, color='#3498db')
    plt.axhline(p_value, color='red', linestyle='--', linewidth=2.5, 
                label=f'{PERCENTILE}th Percentile (${p_value:,.0f} USDT)')
    plt.yscale('log')
    
    plt.title(f'Pair Total 7-Day Volume - Sorted Highest to Lowest Rank\n'
              f'Strong Cointegration + Non-Noise Pairs ({PERCENTILE}th Percentile Marked)', 
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
    print(f"\n✅ DONE! Final file: {output_file} ({len(df):,} rows, sorted highest → lowest)")
    print(f"   Chart: {chart_file} ({PERCENTILE}th percentile marked)")
    if skip_fetch:
        print("   (Used existing volume data — no new API calls)")
