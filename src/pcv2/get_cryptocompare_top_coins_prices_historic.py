import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time
import os
from requests.exceptions import RequestException, Timeout, ConnectionError, ReadTimeout

# ====================== CONFIG ======================
FORCE_REDOWNLOAD = False  # ← Change to True only when you want fresh data for everything
# ===================================================

# Coinbase ticker overrides
COINBASE_SYMBOL_MAP = {
    'MNT': 'MANTLE',
    'PI': 'PI',
}


def get_top_symbols(n: int = 100) -> list:
    """Robust parser — now correctly includes M (MemeCore)."""
    txt_file = f"gecko_top_{n}_non_stable_coins.txt"
    symbols = []
    with open(txt_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or not line[0].isdigit():
                continue
            parts = line.split()
            for i, part in enumerate(parts):
                if part.startswith("$"):
                    if i > 0:
                        symbol = parts[i-1]
                        if symbol.isalnum() and len(symbol) >= 1 and symbol.isupper():
                            if symbol not in symbols:
                                symbols.append(symbol)
                    break
    return symbols


def fetch_crypto_hourly_1year(symbol: str, api_key: str) -> tuple[pd.DataFrame, str]:
    """Smart fallback + partial data saving on timeout/connection errors"""
    symbol = symbol.upper().strip()
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    
    attempts = [
        ('USD', None),
        ('USDT', None),
        ('USDT', 'Binance'),
        ('USDT', 'Bybit'),
        ('USDT', 'OKX'),
        ('USDT', 'Gate.io'),
        ('USDT', 'KuCoin'),
        ('USD', 'Coinbase'),
        ('USDT', 'Coinbase'),
    ]
    
    all_data = []
    used_source = None
    is_partial = False
    
    for base, exchange in attempts:
        fsym = COINBASE_SYMBOL_MAP.get(symbol, symbol) if exchange == 'Coinbase' else symbol
        source_name = f"{base} CCCAGG" if exchange is None else f"{base} on {exchange}"
        if fsym != symbol:
            source_name += f" (as {fsym})"
        
        print(f"   🚀 Fetching {symbol} (trying {source_name})...")
        
        all_data = []
        to_ts = int(datetime.now().timestamp())
        target_start = int((datetime.now() - timedelta(days=390)).timestamp())
        
        success = False
        for i in range(10):
            params = {
                'fsym': fsym,
                'tsym': base,
                'limit': 2000,
                'toTs': to_ts,
                'api_key': api_key.strip()
            }
            if exchange:
                params['e'] = exchange
            
            try:
                response = requests.get(url, params=params, timeout=45)
            except (Timeout, ReadTimeout, ConnectionError) as e:
                print(f"   ⚠️  Timeout during batch {i+1} - saving partial data collected so far")
                if all_data:
                    is_partial = True
                    success = True
                    break
                else:
                    raise
            except RequestException as e:
                raise
            
            if response.status_code != 200:
                raise ConnectionError(f"HTTP {response.status_code} for {symbol}")
            
            data = response.json()
            if data.get('Response') != 'Success':
                msg = data.get('Message', 'Unknown error')
                print(f"   ⚠️  {source_name}: {msg}")
                
                if "CCCAGG market does not exist" in msg and exchange is None:
                    break
                if not all_data and exchange is not None:
                    break
                raise Exception(f"API error for {symbol}: {msg}")
            
            batch = data['Data']['Data']
            if not batch:
                break
                
            all_data.extend(batch)
            
            oldest_ts = batch[0]['time']
            to_ts = oldest_ts - 1
            
            print(f"     Batch {i+1}: +{len(batch):,} records | Oldest: {datetime.fromtimestamp(oldest_ts)}")
            
            if oldest_ts < target_start:
                success = True
                break
            time.sleep(0.65)
        
        if success or all_data:
            used_source = source_name + (" (partial - timeout)" if is_partial else "")
            break
    
    if not all_data:
        raise ValueError(f"{symbol} has no hourly data on CryptoCompare (tried CCCAGG + 7 exchanges including Coinbase)")
    
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    cutoff = pd.Timestamp(datetime.now() - timedelta(days=365), tz='UTC')
    df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    original_rows = len(df)
    df = df[
        (df['open'] > 0) &
        (df['high'] > 0) &
        (df['low'] > 0) &
        (df['close'] > 0)
    ].reset_index(drop=True)
    
    dropped = original_rows - len(df)
    if dropped > 0:
        print(f"   🧹 Dropped {dropped:,} zero-price rows")
    
    actual_days = (df['datetime'].max() - df['datetime'].min()).days if not df.empty else 0
    print(f"   ✅ {symbol}: {len(df):,} valid hourly candles ({actual_days} days) → {used_source}")
    
    return df, used_source


# ====================== RUN IT ======================
if __name__ == "__main__":
    # === Command line argument support (your requested feature) ===
    n_coins = 100
    if len(sys.argv) > 1:
        try:
            n_coins = int(sys.argv[1])
            if n_coins < 1 or n_coins > 2000:
                raise ValueError
        except ValueError:
            print("❌ Usage: python get_cryptocompare_top_coins_prices_historic.py [N]")
            print("   N = number of top coins (default: 100)")
            print("Example: python get_cryptocompare_top_coins_prices_historic.py 200")
            sys.exit(1)

    base_name = f"top{n_coins}_hourly_1year"
    giant_file = f"{base_name}_combined.csv"
    
    print(f"🚀 CryptoCompare Top-{n_coins} → raw_data/ folder + GIANT combined CSV")
    print("   💡 Skips existing files (set FORCE_REDOWNLOAD = True to refresh)")
    print("   ✨ Coinbase fixes + 3-part TXT backup + skip-download option\n")
    
    # === DYNAMIC BACKUP FILES ===
    backup_files = [
        f"{base_name}_combined_backup_1.txt",
        f"{base_name}_combined_backup_2.txt",
        f"{base_name}_combined_backup_3.txt"
    ]
    
    use_backup = False
    if all(os.path.exists(f) for f in backup_files):
        print("📂 Backup files detected!")
        choice = input("   Skip download and load data from backup instead? (y/n): ").strip().lower()
        if choice in ['y', 'yes', '']:
            use_backup = True
    
    all_dfs = []
    success = 0
    failed = []
    fallback_coins = []
    combined = None
    
    if use_backup:
        print("✅ Loading data from 3-part backup...")
        try:
            dfs = [pd.read_csv(f) for f in backup_files]
            combined = pd.concat(dfs, ignore_index=True)
            combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
            combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
            
            combined.to_csv(giant_file, index=False)
            
            print(f"🎉 Loaded {len(combined):,} rows ({combined['symbol'].nunique()} coins) from backup")
            print(f"   Giant CSV saved → {giant_file}")
            
            n = len(combined)
            chunk_size = (n + 2) // 3
            for i in range(3):
                start = i * chunk_size
                end = min(start + chunk_size, n)
                chunk = combined.iloc[start:end]
                backup_file = f"{base_name}_combined_backup_{i+1}.txt"
                chunk.to_csv(backup_file, index=False)
            
            success = combined['symbol'].nunique()
            all_dfs = [combined]
            
        except Exception as e:
            print(f"❌ Failed to load backup: {e}")
            use_backup = False
    
    # ====================== NORMAL DOWNLOAD MODE ======================
    if not use_backup:
        api_key = input("Paste your CryptoCompare API key and press Enter: ").strip()
        if not api_key:
            print("❌ ERROR: API key required.")
            sys.exit(1)
        
        os.makedirs("raw_data", exist_ok=True)
        print("📁 Created/verified folder: raw_data/\n")
        
        symbols = get_top_symbols(n_coins)
        print(f"📋 Parsed {len(symbols)} coins from gecko_top_{n_coins}_non_stable_coins.txt\n")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i:3d}/{len(symbols)}] {symbol}")
            
            individual_file = f"raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv"
            
            if os.path.exists(individual_file) and not FORCE_REDOWNLOAD:
                print("   📂 File already exists → loading from disk")
                try:
                    df = pd.read_csv(individual_file)
                    if 'datetime' in df.columns:
                        df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                    if 'symbol' not in df.columns:
                        df['symbol'] = symbol
                    all_dfs.append(df)
                    success += 1
                    print(f"   ✅ Loaded existing data: {len(df):,} hourly candles\n")
                    continue
                except Exception as e:
                    print(f"   ⚠️  Could not load existing file ({e}). Re-downloading...\n")
            
            try:
                df, used_source = fetch_crypto_hourly_1year(symbol, api_key)
                df['symbol'] = symbol
                
                df.to_csv(individual_file, index=False)
                
                all_dfs.append(df)
                success += 1
                
                if "on " in used_source or "(partial" in used_source:
                    fallback_coins.append((symbol, used_source))
                
                print(f"   💾 Saved → raw_data/{symbol.lower()}_hourly_1year_cryptocompare.csv\n")
            except Exception as e:
                print(f"   ❌ Skipped: {e}\n")
                failed.append(symbol)
            
            time.sleep(1.8)
        
        # ====================== CREATE GIANT CSV + 3-PART BACKUP ======================
        if all_dfs:
            print("🔄 Creating ONE GIANT combined CSV + 3-part TXT backup...")
            combined = pd.concat(all_dfs, ignore_index=True)
            combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
            combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
            
            combined.to_csv(giant_file, index=False)
            
            n = len(combined)
            chunk_size = (n + 2) // 3
            print(f"   📋 Splitting into 3 backup files (~{chunk_size:,} rows each)...")
            
            for i in range(3):
                start = i * chunk_size
                end = min(start + chunk_size, n)
                chunk = combined.iloc[start:end]
                backup_file = f"{base_name}_combined_backup_{i+1}.txt"
                chunk.to_csv(backup_file, index=False)
                print(f"      • Part {i+1}: {backup_file} ({len(chunk):,} rows)")
    
    # ====================== FINAL SUMMARY ======================
    print(f"\n🎉 FINISHED!")
    print(f"   Giant file saved → {giant_file}")
    if combined is not None:
        print(f"   Total rows: {len(combined):,} (≈ {len(combined)//max(success,1):,} hours × {success} coins)")
    print(f"   Successfully processed: {success} coins")
    
    if failed:
        print(f"\n⚠️  Failed coins ({len(failed)}): {', '.join(failed)}")
    
    if fallback_coins:
        print("\n⚠️  WARNING: Some coins used exchange-specific or partial data:")
        for sym, src in fallback_coins:
            print(f"   • {sym} → {src}")
        
        fallback_warning = f"{base_name}_fallback_coins_warning.txt"
        with open(fallback_warning, "w", encoding="utf-8") as f:
            f.write("FALLBACK COINS REPORT\n")
            for sym, src in fallback_coins:
                f.write(f"• {sym} → {src}\n")
        print(f"   💾 Warning report saved → {fallback_warning}")
    
    print("\n📂 Final structure:")
    print("   • raw_data/                          ← individual CSVs")
    print(f"   • {giant_file}")
    for i in range(1, 4):
        print(f"   • {base_name}_combined_backup_{i}.txt")
    print(f"   • {base_name}_fallback_coins_warning.txt (if any)")
