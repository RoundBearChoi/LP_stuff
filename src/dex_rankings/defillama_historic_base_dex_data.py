import requests
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from datetime import datetime

# Get the run date once (used in both chart titles)
run_date = datetime.now().strftime("%B %d, %Y")

print("Fetching latest top 10 DEXes on Base from DefiLlama...")

# Official DefiLlama endpoint
response = requests.get("https://api.llama.fi/overview/dexs/base")
response.raise_for_status()
data = response.json()

protocols = data.get("protocols", [])

# Extract and clean
dex_list = []
for p in protocols:
    name = p.get("displayName") or p.get("name", "Unknown")
    vol24h = p.get("volume24h") or p.get("total24h") or 0
    vol7d  = p.get("volume7d")  or p.get("total7d")  or 0
    vol30d = p.get("volume30d") or p.get("total30d") or 0
    
    if vol24h > 100_000:  # filter noise
        dex_list.append({
            "name": name,
            "volume_24h": float(vol24h),
            "volume_7d": float(vol7d),
            "volume_30d": float(vol30d)
        })

df = pd.DataFrame(dex_list)
df = df.sort_values(by="volume_24h", ascending=False).head(10).reset_index(drop=True)

print("\nTop 10 DEXes on Base (by 24h volume):")
print(df[["name", "volume_24h", "volume_7d", "volume_30d"]].round(0).to_string(index=False))

def create_chart(period_days, filename, palette):
    plt.figure(figsize=(12, 8))
    sns.set_style("whitegrid")
    
    vol_col = f"volume_{period_days}d"
    df_plot = df.copy()
    
    # Sort so bars go biggest → smallest (top to bottom)
    df_plot = df_plot.sort_values(by=vol_col, ascending=False).reset_index(drop=True)
    df_plot["billions"] = df_plot[vol_col] / 1_000_000_000
    
    # Modern seaborn syntax (no FutureWarning)
    ax = sns.barplot(
        x="billions", 
        y="name", 
        hue="name",
        data=df_plot, 
        palette=palette, 
        edgecolor="black",
        legend=False
    )
    
    # === NEW: Date added to title ===
    plt.title(f"Top 10 DEXes on Base — {period_days}D Volume (as of {run_date})",
              fontsize=16, pad=20)
    
    plt.xlabel("Trading Volume (Billions USD)", fontsize=13)
    plt.ylabel("")
    
    # Value labels
    for i, v in enumerate(df_plot["billions"]):
        ax.text(v + 0.15, i, f"${v:.2f}B", va="center", fontsize=11, fontweight="bold")
    
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"✓ Saved: {filename}")

# Generate the two charts
create_chart(7,  "base_top10_7d_volume.png",  "Blues_r")
create_chart(30, "base_top10_30d_volume.png", "Greens_r")

print(f"\nDone! Charts generated as of {run_date}")
