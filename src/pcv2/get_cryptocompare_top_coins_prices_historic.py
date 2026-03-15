import requests
import pandas as pd
from datetime import datetime, timedelta
import sys
import time
import os
from requests.exceptions import RequestException, Timeout, ConnectionError, ReadTimeout
import math

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


def fetch_crypto_hourly(symbol: str, months: int, api_key: str, fetch_all: bool = False) -> tuple[pd.DataFrame, str]:
    """Smart fallback + partial data saving.
    Now with DYNAMIC batch count so 32, 60, 84, or 120 months all work perfectly."""
    symbol = symbol.upper().strip()
    url = "https://min-api.cryptocompare.com/data/v2/histohour"
    
    attempts = [
        ('USD', None), ('USDT', None),
        ('USDT', 'Binance'), ('USDT', 'Bybit'), ('USDT', 'OKX'),
        ('USDT', 'Gate.io'), ('USDT', 'KuCoin'),
        ('USD', 'Coinbase'), ('USDT', 'Coinbase'),
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
        
        # === DYNAMIC BATCH CALCULATION (this removes the old 12-batch hard limit) ===
        if fetch_all:
            target_start = int(datetime(2010, 1, 1).timestamp())
            max_batches = 80
            print(f"   📜 FULL HISTORY MODE for {symbol}...")
        else:
            hours_needed = months * 30.5 * 24 + 500          # buffer
            batches_needed = math.ceil(hours_needed / 2000) + 5
            max_batches = max(15, min(60, batches_needed))   # safe range
            buffer_days = int(months * 30.5) + 40
            target_start = int((datetime.now() - timedelta(days=buffer_days)).timestamp())
            print(f"   📅 Requesting {months} months → will use up to {max_batches} batches")
        
        success = False
        for i in range(max_batches):
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
        raise ValueError(f"{symbol} has no hourly data on CryptoCompare (tried CCCAGG + exchanges)")
    
    df = pd.DataFrame(all_data)
    df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
    df = df.sort_values('time').reset_index(drop=True)
    
    if not fetch_all:
        cutoff = pd.Timestamp(datetime.now() - timedelta(days=months * 30.5), tz='UTC')
        df = df[df['datetime'] >= cutoff].reset_index(drop=True)
    
    df = df[['datetime', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
    
    original_rows = len(df)
    df = df[(df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)].reset_index(drop=True)
    dropped = original_rows - len(df)
    if dropped > 0:
        print(f"   🧹 Dropped {dropped:,} zero-price rows")
    
    actual_days = (df['datetime'].max() - df['datetime'].min()).days if not df.empty else 0
    actual_years = actual_days / 365.25
    print(f"   ✅ {symbol}: {len(df):,} valid hourly candles (~{actual_years:.1f} years) → {used_source}")
    
    return df, used_source


# ====================== RUN IT ======================
if __name__ == "__main__":
    n_coins = 100
    months = 12
    fetch_all = False

    if len(sys.argv) > 1:
        try:
            n_coins = int(sys.argv[1])
            if n_coins < 1 or n_coins > 2000:
                raise ValueError
        except ValueError:
            print("❌ Usage: python get_cryptocompare_top_coins_prices_historic.py [N_COINS] [MONTHS]")
            print("   MONTHS = 0 for FULL HISTORY, or any number 1–240")
            print("Example: python ... 100 32")
            print("         python ... 100 0     ← full history")
            sys.exit(1)

    if len(sys.argv) > 2:
        try:
            months = int(sys.argv[2])
            if months < 0 or months > 240:
                raise ValueError
            if months == 0:
                fetch_all = True
        except ValueError:
            print("❌ MONTHS must be 0–240 (0 = full history)")
            sys.exit(1)

    if fetch_all:
        base_name = f"top{n_coins}_hourly_FULLHISTORY"
        print("📜 FULL HISTORY MODE ENABLED")
    else:
        base_name = f"top{n_coins}_hourly_{months}months"
    
    giant_file = f"{base_name}_combined.csv"
    
    print(f"🚀 CryptoCompare Top-{n_coins} coins → {'FULL HISTORY' if fetch_all else f'{months} months history'}")
    print("   💡 Skips existing files (FORCE_REDOWNLOAD = True to refresh)\n")
    
    # === DYNAMIC BACKUP FILES (unchanged) ===
    backup_files = [f"{base_name}_combined_backup_{i+1}.txt" for i in range(1,4)]
    
    use_backup = False
    if all(os.path.exists(f) for f in backup_files):
        print("📂 Backup files detected!")
        choice = input("   Skip download and load from backup? (y/n): ").strip().lower()
        if choice in ['y', 'yes', '']:
            use_backup = True
    
    all_dfs = []
    success = 0
    failed = []
    fallback_coins = []
    combined = None
    
    if use_backup:
        # ... (exactly the same backup loading code as before — omitted here for brevity but it's unchanged) ...
        try:
            dfs = [pd.read_csv(f) for f in backup_files]
            combined = pd.concat(dfs, ignore_index=True)[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
            combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
            combined.to_csv(giant_file, index=False)
            print(f"🎉 Loaded {len(combined):,} rows from backup")
            success = combined['symbol'].nunique()
            all_dfs = [combined]
            # re-save 3-part backups
            n = len(combined)
            chunk_size = (n + 2) // 3
            for i in range(3):
                chunk = combined.iloc[i*chunk_size:(i+1)*chunk_size]
                chunk.to_csv(backup_files[i], index=False)
        except Exception as e:
            print(f"❌ Backup load failed: {e}")
            use_backup = False
    
    if not use_backup:
        api_key = input("Paste your CryptoCompare API key: ").strip()
        if not api_key:
            print("❌ API key required.")
            sys.exit(1)
        
        os.makedirs("raw_data", exist_ok=True)
        symbols = get_top_symbols(n_coins)
        print(f"📋 Parsed {len(symbols)} coins\n")
        
        for i, symbol in enumerate(symbols, 1):
            print(f"[{i:3d}/{len(symbols)}] {symbol}")
            individual_file = f"raw_data/{symbol.lower()}_hourly_{'FULL' if fetch_all else months}months_cryptocompare.csv"
            
            if os.path.exists(individual_file) and not FORCE_REDOWNLOAD:
                df = pd.read_csv(individual_file)
                if 'datetime' in df.columns:
                    df['datetime'] = pd.to_datetime(df['datetime'], utc=True)
                if 'symbol' not in df.columns:
                    df['symbol'] = symbol
                all_dfs.append(df)
                success += 1
                print(f"   ✅ Loaded existing: {len(df):,} candles\n")
                continue
            
            try:
                df, used_source = fetch_crypto_hourly(symbol, months, api_key, fetch_all)
                df['symbol'] = symbol
                df.to_csv(individual_file, index=False)
                all_dfs.append(df)
                success += 1
                if "on " in used_source or "(partial" in used_source:
                    fallback_coins.append((symbol, used_source))
                print(f"   💾 Saved → {individual_file}\n")
            except Exception as e:
                print(f"   ❌ Skipped: {e}\n")
                failed.append(symbol)
            
            time.sleep(1.8)
        
        if all_dfs:
            print("🔄 Creating giant CSV + 3-part backups...")
            combined = pd.concat(all_dfs, ignore_index=True)[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
            combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
            combined.to_csv(giant_file, index=False)
            
            n = len(combined)
            chunk_size = (n + 2) // 3
            for i in range(3):
                chunk = combined.iloc[i*chunk_size:(i+1)*chunk_size]
                chunk.to_csv(backup_files[i], index=False)
                print(f"      • Part {i+1}: {backup_files[i]} ({len(chunk):,} rows)")

    # ====================== FINAL SUMMARY ======================
    print(f"\n🎉 FINISHED! Giant file → {giant_file}")
    if combined is not None:
        print(f"   Total rows: {len(combined):,} (~{len(combined)//max(success,1):,} hours × {success} coins)")
    print(f"   Success: {success} coins")
    if failed:
        print(f"⚠️  Failed: {len(failed)} coins → {', '.join(failed)}")
    if fallback_coins:
        print("⚠️  Some coins used fallback sources (saved warning file)")
    
    print("\n📂 Files ready:")
    print("   • raw_data/ (individual CSVs)")
    print(f"   • {giant_file}")
    print("   • 3 backup .txt files")
