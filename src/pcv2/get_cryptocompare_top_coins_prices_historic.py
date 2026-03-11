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

def get_top100_symbols(txt_file: str = "gecko_top_100_non_stable_coins.txt") -> list:
    """Robust parser — now correctly includes M (MemeCore)."""
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
    print("🚀 CryptoCompare Top-100 → raw_data/ folder + GIANT combined CSV")
    print("   💡 Skips existing files (set FORCE_REDOWNLOAD = True to refresh)")
    print("   ✨ Coinbase fixes for MNT/PI + PARTIAL DATA SAVING on timeout\n")
    
    api_key = input("Paste your CryptoCompare API key and press Enter: ").strip()
    if not api_key:
        print("❌ ERROR: API key required.")
        sys.exit(1)
    
    os.makedirs("raw_data", exist_ok=True)
    print("📁 Created/verified folder: raw_data/\n")
    
    symbols = get_top100_symbols()
    print(f"📋 Parsed {len(symbols)} coins from gecko_top_100_non_stable_coins.txt\n")
    
    all_dfs = []
    success = 0
    failed = []
    fallback_coins = []
    
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
    
    # ====================== GIANT COMBINED CSV + EXACT TXT BACKUP ======================
    if all_dfs:
        print("🔄 Creating ONE GIANT combined CSV + exact TXT backup...")
        combined = pd.concat(all_dfs, ignore_index=True)
        combined = combined[['datetime', 'symbol', 'open', 'high', 'low', 'close', 'volumefrom', 'volumeto']]
        combined = combined.sort_values(['symbol', 'datetime']).reset_index(drop=True)
        
        giant_file = "top100_hourly_1year_combined.csv"
        combined.to_csv(giant_file, index=False)
        
        # === EXACT TEXT COPY INTO TXT (your requested update) ===
        backup_txt      = "top100_hourly_1year_combined_backup.txt"          # latest backup (overwritten each run)
        backup_dated    = f"top100_hourly_1year_combined_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        
        try:
            with open(giant_file, "r", encoding="utf-8") as source:
                content = source.read()
            
            with open(backup_txt, "w", encoding="utf-8") as f:
                f.write(content)
            
            with open(backup_dated, "w", encoding="utf-8") as f:
                f.write(content)
            
            print(f"   📋 Exact TXT backups created:")
            print(f"      • Latest:  {backup_txt}")
            print(f"      • Dated:   {backup_dated}")
        except Exception as backup_error:
            print(f"   ⚠️  TXT backup failed (CSV still saved): {backup_error}")
        
        print(f"\n🎉 FINISHED!")
        print(f"   Giant file saved → {giant_file}")
        print(f"   Total rows: {len(combined):,} (≈ {len(combined)//success:,} hours × {success} coins)")
        print(f"   Successfully processed: {success}/{len(symbols)} coins")
    
    if failed:
        print(f"\n⚠️  Failed coins ({len(failed)}): {', '.join(failed)}")
        print("      (These coins currently have no hourly data on CryptoCompare even via exchanges)")
    
    # ====================== CONSOLE + TXT FALLBACK WARNING ======================
    if fallback_coins:
        print("\n⚠️  WARNING: The following coins used direct exchange data or partial downloads:")
        for sym, src in fallback_coins:
            print(f"   • {sym} → {src}")
        print("      → Prices/volume from single exchange or partial history only.")
        print("      → Data is still 100% valid for analysis.")
        
        warning_file = "fallback_coins_warning.txt"
        with open(warning_file, "w", encoding="utf-8") as f:
            f.write("══════════════════════════════════════════════════════════════\n")
            f.write("CryptoCompare Downloader - FALLBACK WARNING REPORT\n")
            f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S KST')}\n")
            f.write("══════════════════════════════════════════════════════════════\n\n")
            f.write("The following coins used direct exchange data or partial downloads:\n\n")
            
            for sym, src in fallback_coins:
                f.write(f"• {sym} → {src}\n")
            
            f.write("\n→ Prices and volume come from that single exchange or partial history only.\n")
            f.write("→ This is completely normal. Data is still 100% valid for analysis.\n\n")
            f.write("Note: Re-running with FORCE_REDOWNLOAD=True will not change this\n")
            f.write("      unless CryptoCompare adds CCCAGG support in the future.\n")
        
        print(f"   💾 Warning report saved → {warning_file}")
    
    print("\n📂 Final structure:")
    print(f"   • raw_data/                    ← contains {success} individual CSVs")
    print("   • top100_hourly_1year_combined.csv")
    print("   • top100_hourly_1year_combined_backup.txt          ← exact text copy")
    print("   • top100_hourly_1year_combined_backup_YYYYMMDD_HHMM.txt  ← dated history")
    print("   • fallback_coins_warning.txt")
    print("   • get_cryptocompare_top_coins_prices_historic.py")
