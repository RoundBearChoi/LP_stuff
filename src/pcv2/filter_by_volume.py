import pandas as pd
import requests
import time
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime


class VolumeFilter:
    """Processes cointegration pairs and adds/ranks by 7-day volume from MEXC + KuCoin."""

    def __init__(self, 
        # ====================== CONFIG (change these!) ======================
                 PERCENTILE: int = 5,
                 MIN_VOLUME_RATIO: float = 0.0001, # most will not fall under imbalanced for now
                 VOLUME_CACHE_FILE: str = "mexc_kucoin_volume.csv"):
        # ===========================================================================
        self.PERCENTILE = PERCENTILE
        self.MIN_VOLUME_RATIO = MIN_VOLUME_RATIO
        self.VOLUME_CACHE_FILE = VOLUME_CACHE_FILE

    def ordinal(self, n: int) -> str:
        """Proper English suffixes: 1st, 2nd, 3rd, 4th..."""
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
        return f"{n}{suffix}"

    def get_mexc_7d_avg_volume(self, symbol):
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

    def get_kucoin_7d_avg_volume(self, symbol):
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

    def load_volume_cache(self):
        if os.path.exists(self.VOLUME_CACHE_FILE):
            df_cache = pd.read_csv(self.VOLUME_CACHE_FILE)
            print(f"✅ Loaded existing volume cache with {len(df_cache):,} symbols")
            return df_cache
        else:
            print(f"📂 No volume cache found → will create {self.VOLUME_CACHE_FILE}")
            return pd.DataFrame(columns=['symbol', 'mexc_7d_avg_vol_usdt', 'kucoin_7d_avg_vol_usdt', 'last_updated'])

    def save_volume_cache(self, df_cache):
        df_cache.to_csv(self.VOLUME_CACHE_FILE, index=False)
        print(f"💾 Saved/updated volume cache → {self.VOLUME_CACHE_FILE} ({len(df_cache):,} symbols)")

    def run(self, input_file: str = "filtered_by_stability_johansen_one_direction_18m_top42778.csv"):
        output_file = input_file.replace("stability", "volume")
        
        if not os.path.exists(input_file):
            print(f"❌ Original file '{input_file}' not found!")
            return

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
        volume_cache_df = self.load_volume_cache()
        cached_symbols = set(volume_cache_df['symbol'].astype(str).str.upper())
        
        # Find symbols we still need to fetch
        missing_symbols = [str(s).strip().upper() for s in symbols 
                           if str(s).strip().upper() not in cached_symbols]
        
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
                mexc_vol = self.get_mexc_7d_avg_volume(sym)
                kucoin_vol = self.get_kucoin_7d_avg_volume(sym)
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
                self.save_volume_cache(volume_cache_df)
        
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
        
        # ====================== VOLUME FLAG (NO ROWS DROPPED) ======================
        print(f"🔍 Adding volume_flag column (using {self.MIN_VOLUME_RATIO*100:.0f}% balance threshold)...")
        v1 = df['symbol1_total_7d_vol_usdt']
        v2 = df['symbol2_total_7d_vol_usdt']
        v_cols = ['symbol1_total_7d_vol_usdt', 'symbol2_total_7d_vol_usdt']
        
        df['volume_flag'] = "balanced"                                      # default
        df.loc[(v1 == 0) | (v2 == 0), 'volume_flag'] = "zero_volume"
        df.loc[
            (v1 > 0) & (v2 > 0) &
            (df[v_cols].min(axis=1) < self.MIN_VOLUME_RATIO * df[v_cols].max(axis=1)),
            'volume_flag'
        ] = "imbalanced"
        
        print(f"   → Balanced pairs     : {len(df[df['volume_flag'] == 'balanced']):,}")
        print(f"   → Imbalanced pairs   : {len(df[df['volume_flag'] == 'imbalanced']):,}")
        print(f"   → Zero-volume pairs  : {len(df[df['volume_flag'] == 'zero_volume']):,}")
        # ===========================================================================

        # ====================== RANK BALANCED ONLY + MARK LOW VOLUME ======================
        print("\n🔄 Ranking balanced pairs only (imbalanced/zero moved to bottom)...")
        balanced_df = df[df['volume_flag'] == 'balanced'].copy()
        other_df = df[df['volume_flag'] != 'balanced'].copy()

        if not balanced_df.empty:
            # Rank only balanced pairs
            balanced_df = balanced_df.sort_values(by='pair_total_7d_vol_usdt', ascending=False).reset_index(drop=True)
            balanced_df['volume_percentile'] = (balanced_df['pair_total_7d_vol_usdt'].rank(pct=True) * 100).round(2)
            balanced_df['volume_percentile_rank'] = balanced_df['volume_percentile'].round(0).astype(int).map(self.ordinal) + " percentile"
            
            p_value = balanced_df['pair_total_7d_vol_usdt'].quantile(self.PERCENTILE / 100.0)
            
            # Mark lower volume after ranking (exactly as you asked)
            balanced_df['volume_level'] = np.where(
                balanced_df['volume_percentile'] <= self.PERCENTILE,
                'low_volume',
                'high_volume'
            )
            print(f"   → high_volume (balanced) : {len(balanced_df[balanced_df['volume_level']=='high_volume']):,}")
            print(f"   → low_volume  (balanced) : {len(balanced_df[balanced_df['volume_level']=='low_volume']):,}")
        else:
            p_value = 0.0

        # Sort non-balanced and prepare for bottom
        if not other_df.empty:
            other_df = other_df.sort_values(by='pair_total_7d_vol_usdt', ascending=False).reset_index(drop=True)
            other_df['volume_level'] = 'excluded'
            other_df['volume_percentile'] = np.nan
            other_df['volume_percentile_rank'] = ''

        # Final DataFrame: balanced ranked at top + others at bottom
        df = pd.concat([balanced_df, other_df], ignore_index=True)
        print(f"📈 {self.PERCENTILE}th percentile total volume (balanced pairs only): ${p_value:,.0f} USDT")
        # ===========================================================================

        # ====================== CHART (BALANCED ONLY) ======================
        print(f"📈 Generating sorted rank chart ({self.PERCENTILE}th percentile, excluding imbalanced and zero balance)...")
        if not balanced_df.empty:
            volumes = balanced_df['pair_total_7d_vol_usdt']
            ranks = range(1, len(balanced_df) + 1)
            plot_volumes = np.maximum(volumes, 1)
            
            plt.figure(figsize=(14, 8), dpi=150)
            plt.plot(ranks, plot_volumes, linewidth=2, color='#3498db')
            plt.axhline(p_value, color='red', linestyle='--', linewidth=2.5, 
                        label=f'{self.PERCENTILE}th Percentile (${p_value:,.0f} USDT)')
            plt.yscale('log')
            
            plt.title(f'Pair Total 7-Day Volume - Sorted Highest to Lowest Rank\n'
                      f'Strong Cointegration + Non-Noise (Balanced pairs only - excluding imbalanced & zero_volume)', 
                      fontsize=14, pad=20)
            plt.xlabel('Pair Rank (1 = Highest Total Volume)')
            plt.ylabel('Pair Total Volume USDT (log scale)')
            plt.legend(fontsize=12)
            plt.grid(True, alpha=0.3)
            
            chart_file = "pair_total_volume_sorted_rank_balanced.png"
            plt.savefig(chart_file, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"   ✅ Chart saved → {chart_file}")
        else:
            print("   ⚠️  No balanced pairs → chart skipped")
        # ===========================================================================

        # Reorder columns (volume columns right after pair_total)
        cols = list(df.columns)
        try:
            total_idx = cols.index('pair_total_7d_vol_usdt')
            for col in ['volume_flag', 'volume_level', 'volume_percentile_rank', 'volume_percentile'][::-1]:
                if col in cols:
                    cols.insert(total_idx + 1, cols.pop(cols.index(col)))
            df = df[cols]
        except:
            pass
        
        # Save the final filtered/ranked results
        df.to_csv(output_file, index=False)
        print(f"\n✅ DONE!")
        print(f"   Final file → {output_file} ({len(df):,} rows) ← NO pairs were dropped!")
        print(f"   Volume cache → {self.VOLUME_CACHE_FILE} ({len(volume_cache_df):,} symbols)")
        print(f"   Top = ranked balanced pairs | Bottom = imbalanced + zero_volume")
        print(f"   New column: volume_level → 'high_volume' / 'low_volume' / 'excluded'")


if __name__ == "__main__":
    processor = VolumeFilter()          # you can override any config here, e.g. VolumeFilter(PERCENTILE=20)
    processor.run()                     # or pass a custom input_file: processor.run("my_other_file.csv")
