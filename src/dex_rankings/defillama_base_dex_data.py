import requests
import pandas as pd
from datetime import datetime
import os
import matplotlib.pyplot as plt
from pathlib import Path

# ==================== CONFIG ====================
CSV_FILE = "base_dex_volume_log.csv"
HIGHLIGHT_DEX = "Aerodrome"          # Change to "PancakeSwap" or "Uniswap V3" if you want
PLOT_ON_RUN = False                  # Set True to auto-show chart every run
# ==============================================

def fetch_dex_data():
    """Fetch latest Base DEX data from DefiLlama API"""
    url = "https://api.llama.fi/overview/dexs/base"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ API error: {e}")
        return None

def process_data(raw_data):
    """Handle changing column names + debug print"""
    protocols = raw_data.get("protocols", [])
    if not protocols:
        raise ValueError("No protocols data in API response")

    df = pd.DataFrame(protocols)
    
    print(f"🔍 Available columns in API response: {df.columns.tolist()}\n")
    
    # Flexible column detection (handles DefiLlama changes)
    vol_24h_col = next((col for col in ["dailyVolume", "volume24h", "total24h"] if col in df.columns), None)
    vol_7d_col = next((col for col in ["volume7d", "totalVolume7d", "total7d"] if col in df.columns), None)
    change_col = next((col for col in ["change_1d", "change1d", "dailyChange"] if col in df.columns), None)

    if not vol_24h_col:
        raise ValueError(f"Could not find 24h volume column. Available: {df.columns.tolist()}")

    print(f"✅ Using columns → 24h: '{vol_24h_col}' | 7d: '{vol_7d_col}' | Change: '{change_col or 'N/A'}'")

    # Select needed columns
    cols = ["name", vol_24h_col]
    if vol_7d_col:
        cols.append(vol_7d_col)
    if change_col:
        cols.append(change_col)
    
    df = df[cols].copy()

    # Rename for internal consistency
    rename_map = {vol_24h_col: "volume24h"}
    if vol_7d_col:
        rename_map[vol_7d_col] = "volume7d"
    if change_col:
        rename_map[change_col] = "change_1d"
    df = df.rename(columns=rename_map)

    # Calculations
    total_24h = df["volume24h"].sum()
    total_7d = df.get("volume7d", pd.Series([0] * len(df))).sum()

    df["share_24h_%"] = (df["volume24h"] / total_24h * 100).round(2)
    df["share_7d_%"] = (df["volume7d"] / total_7d * 100).round(2) if "volume7d" in df.columns else 0.0
    df["change_1d_%"] = (df.get("change_1d", pd.Series([0] * len(df))) * 100).round(2)

    df = df.sort_values("volume24h", ascending=False).reset_index(drop=True)
    
    return df, round(total_24h / 1_000_000, 2), round(total_7d / 1_000_000, 2)

def log_snapshot(df, total_24h_m, total_7d_m):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    aero = df[df["name"] == HIGHLIGHT_DEX]
    aero_share_24h = aero["share_24h_%"].iloc[0] if not aero.empty else 0
    aero_vol_24h = aero["volume24h"].iloc[0] if not aero.empty else 0

    new_row = pd.DataFrame([{
        "timestamp": timestamp,
        "total_24h_volume_m": total_24h_m,
        "aerodrome_24h_volume_m": round(aero_vol_24h / 1_000_000, 2),
        "aerodrome_24h_share_%": aero_share_24h,
        "aerodrome_7d_share_%": aero["share_7d_%"].iloc[0] if not aero.empty else 0,
        "top_dex": df.iloc[0]["name"]
    }])

    header = not os.path.exists(CSV_FILE)
    new_row.to_csv(CSV_FILE, mode="a", header=header, index=False)
    print(f"✓ Snapshot saved to {CSV_FILE} ({timestamp})")

def plot_trend():
    if not os.path.exists(CSV_FILE):
        print("Run the script a few times first to build history!")
        return
    df = pd.read_csv(CSV_FILE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    plt.figure(figsize=(13, 7))
    plt.plot(df["timestamp"], df["aerodrome_24h_share_%"], 
             marker="o", linewidth=3, color="#00D1FF", label="Aerodrome 24h Share")
    plt.title("Aerodrome Market Share on Base — Volume Trend", fontsize=16, fontweight="bold")
    plt.ylabel("Market Share (%)")
    plt.xlabel("Date")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# ==================== MAIN ====================
if __name__ == "__main__":
    print("🔄 Fetching latest Base DEX volume data from DefiLlama...\n")
    
    data = fetch_dex_data()
    if data:
        try:
            df, total_24h_m, total_7d_m = process_data(data)
            
            print(f"Base Total 24h DEX Volume : ${total_24h_m:,}M")
            print(f"Base Total 7d DEX Volume  : ${total_7d_m:,}M\n")
            
            print("=== Top 10 DEXes by 24h Volume (Base) ===")
            print(df.head(10)[["name", "volume24h", "share_24h_%", "change_1d_%"]].to_string(index=False))
            
            aero = df[df["name"] == HIGHLIGHT_DEX]
            if not aero.empty:
                a = aero.iloc[0]
                print(f"\n🚀 {HIGHLIGHT_DEX} 24h: ${a['volume24h']:,.0f} "
                      f"({a['share_24h_%']}%)  —  7d share: {a['share_7d_%']}%")
            
            log_snapshot(df, total_24h_m, total_7d_m)
            
            if PLOT_ON_RUN:
                plot_trend()
            else:
                print("\n💡 Run plot_trend() in Python console to see the chart anytime")
                
        except Exception as e:
            print(f"Processing error: {e}")
    else:
        print("Failed to fetch data — check your internet.")
