import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

print("=== Base DEX 180-Day Market Share Charts + Live Snapshot ===\n")

# ==================== 1. Load your data ====================
df = pd.read_csv('base_dex_180d.csv')
df['day'] = pd.to_datetime(df['day'])

print(f"✅ Loaded {len(df):,} rows → {df['day'].min().date()} to {df['day'].max().date()}")

# ==================== 2. Identify top projects ====================
top_projects = df.groupby('project')['market_share_pct'].mean().nlargest(7).index.tolist()

# ==================== 3. Charts (saved silently) ====================

# 1. Stacked Area Chart
pivot = df.pivot_table(index='day', columns='project', values='market_share_pct', aggfunc='sum').fillna(0)
main = pivot[top_projects].copy()
main['Others'] = 100 - main.sum(axis=1)

plt.figure(figsize=(15, 8))
main.plot.area(alpha=0.85, linewidth=0.8, cmap='tab10')
plt.title('Base Chain DEX Market Share Evolution (Last 180 Days)', fontsize=18, pad=20)
plt.ylabel('Market Share (%)', fontsize=14)
plt.legend(title='DEX Project', bbox_to_anchor=(1.02, 1), loc='upper left')
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('base_dex_stacked_market_share.png', dpi=300, bbox_inches='tight')
print("✅ Saved: base_dex_stacked_market_share.png")

# 2. Top 5 Line Chart
plt.figure(figsize=(15, 7))
top5 = top_projects[:5]
for project in top5:
    data = df[df['project'] == project].sort_values('day')
    plt.plot(data['day'], data['market_share_pct'], label=project, linewidth=2.8)

plt.title('Top 5 Base DEXes — Market Share Trends', fontsize=16)
plt.ylabel('Market Share (%)', fontsize=13)
plt.legend(title='DEX', fontsize=11)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('base_dex_top5_lines.png', dpi=300)
print("✅ Saved: base_dex_top5_lines.png")

# 3. Latest Day Bar Chart WITH % VALUES ON BARS (top 3 bold)
latest_day = df['day'].max()
latest = df[df['day'] == latest_day].nlargest(10, 'market_share_pct').copy()

plt.figure(figsize=(13, 8))
ax = sns.barplot(data=latest, x='market_share_pct', y='project', palette='viridis')

# Add percentage labels directly on the bars
for i, p in enumerate(ax.patches):
    width = p.get_width()
    pct = latest.iloc[i]['market_share_pct']
    if i < 3:  # Top 3 = bold + bigger + black
        ax.text(width + 1.0, p.get_y() + p.get_height()/2, f'{pct:.2f}%',
                va='center', ha='left', fontsize=13.5, fontweight='bold', color='black')
    else:  # Others = clean smaller labels
        ax.text(width + 0.7, p.get_y() + p.get_height()/2, f'{pct:.2f}%',
                va='center', ha='left', fontsize=11, color='darkgray')

plt.title(f'Top DEXes on Base — {latest_day.date()}', fontsize=17, pad=20)
plt.xlabel('Market Share (%)')
plt.ylabel('')
plt.xlim(right=latest['market_share_pct'].max() * 1.22)  # extra space for labels
plt.tight_layout()
plt.savefig('base_dex_latest_bar.png', dpi=300, bbox_inches='tight')
print("✅ Saved: base_dex_latest_bar.png (with % values on bars)")

# ==================== 4. CURRENT TOP 3 SNAPSHOT ====================
print("\n" + "="*72)
print(f"📈 CURRENT BASE DEX LEADERBOARD — {latest_day.date()}")
print("="*72)

top3 = latest.head(3)
for i, row in top3.iterrows():
    rank = ["🥇", "🥈", "🥉"][i]
    print(f"{rank} {row['project'].title():<13} {row['market_share_pct']:6.2f}%   "
          f"(${row['volume_usd']:,.0f} volume)")

total_vol = top3['total_volume'].iloc[0]
print(f"\nTotal Base DEX Volume today: ${total_vol:,.0f}")
print("="*72)

print("\n🎉 All done! The latest bar chart now shows exact % values (top 3 highlighted).")
