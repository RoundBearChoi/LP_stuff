#!/usr/bin/env python3
"""
clean_up_zscore_rank.py

This script processes the filtered cointegration pairs CSV and creates a clean, ranked output
specifically for z-score mean-reversion trading strategies.

WHAT IT DOES:
1. Loads the full dataset (filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv).
2. Identifies the TOP 20th percentile of pairs based on 'balanced_reversion_count' 
   (i.e. the 20% of pairs with the highest number of balanced up/down z-score reversions).
3. Sorts ONLY those top pairs by 'balanced_reversion_consistency_score' (descending – higher consistency first).
4. Marks ALL remaining pairs (the bottom 80%) with the flag 'low balanced reversion count' 
   and moves them to the bottom of the file – no further calculations or sorting are performed on them.
5. Adds two new helpful columns:
   - 'rank_category' – clearly labels high vs low groups
   - 'final_rank' – overall position in the final file (1 = best)
6. Saves everything to a new CSV that is ready for manual review or automated strategy loading.

The script is fully configurable at the top so you can easily change the percentile, 
sorting direction, filenames, or column names if the CSV structure ever changes.

No external dependencies beyond pandas (already available in your environment).
"""

import pandas as pd

# ==================== CONFIG SECTION ====================
# ←←← CHANGE THESE VARIABLES AS NEEDED →→→

# File paths
INPUT_FILE = "filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv"
OUTPUT_FILE = "zscore_ranked_balanced_reversion_top20.csv"

# Ranking rules
TOP_PERCENTILE = 20                     # Top X% by balanced_reversion_count (20 = top 20th percentile)
SORT_BY_COLUMN = "balanced_reversion_consistency_score"
SORT_ASCENDING = False                  # False = highest consistency first (recommended for trading)

# Column names (in case you rename them later)
BALANCED_COUNT_COL = "balanced_reversion_count"
BALANCED_CONSISTENCY_COL = "balanced_reversion_consistency_score"

# Optional: extra columns you want to keep at the front of the output for quick viewing
DISPLAY_COLUMNS_FIRST = [
    "pair",
    "symbol1",
    "symbol2",
    BALANCED_COUNT_COL,
    BALANCED_CONSISTENCY_COL,
    "rank_category",
    "final_rank",
    "reversion_consistency_score",
    "balance_ratio",
    "mean_reversion_interval_days",
    "volume_level",
    "volume_percentile_rank",
]
# ======================================================

print("🚀 Starting z-score ranking cleanup...")

# Load the data
df = pd.read_csv(INPUT_FILE)
print(f"✅ Loaded {len(df):,} pairs with {len(df.columns)} columns.")

# Calculate the exact threshold value for the top X%
threshold = df[BALANCED_COUNT_COL].quantile(1 - TOP_PERCENTILE / 100.0)
print(f"Top {TOP_PERCENTILE}% threshold for '{BALANCED_COUNT_COL}': {threshold:,.2f}")

# Split the dataframe into high-quality and low-quality groups
high_df = df[df[BALANCED_COUNT_COL] >= threshold].copy()
low_df = df[df[BALANCED_COUNT_COL] < threshold].copy()

print(f"   → High-quality pairs (top {TOP_PERCENTILE}%): {len(high_df):,}")
print(f"   → Low-quality pairs (bottom {100 - TOP_PERCENTILE}%): {len(low_df):,}")

# Sort the high-quality group by consistency score (best first)
high_df = high_df.sort_values(by=SORT_BY_COLUMN, ascending=SORT_ASCENDING)

# Mark the groups clearly
high_df["rank_category"] = "high_balanced_reversion"
low_df["rank_category"] = "low balanced reversion count"

# For the low group we do NO extra calculations or sorting – just move them to the bottom.
# (You can change this line if you ever want them sorted by count descending, etc.)
# low_df = low_df.sort_values(by=BALANCED_COUNT_COL, ascending=False)  # ← uncomment if desired

# Combine: high-quality first, then low-quality at the very bottom
final_df = pd.concat([high_df, low_df], ignore_index=True)

# Add an overall rank column (useful for quick reference)
final_df["final_rank"] = range(1, len(final_df) + 1)

# Reorder columns so the most important info appears first
all_columns = DISPLAY_COLUMNS_FIRST + [col for col in final_df.columns if col not in DISPLAY_COLUMNS_FIRST]
final_df = final_df[all_columns]

# Save the result
final_df.to_csv(OUTPUT_FILE, index=False)

print(f"\n🎉 FINISHED!")
print(f"   Output file: {OUTPUT_FILE}")
print(f"   Total rows: {len(final_df):,}")
print(f"   Top 10 highest-quality pairs preview:")
print(final_df.head(10)[["final_rank", "pair", BALANCED_COUNT_COL, BALANCED_CONSISTENCY_COL, "rank_category"]].to_string(index=False))

print("\nThe file is now ready for your z-score strategy. High-quality pairs are at the top, sorted perfectly. Low-count pairs are clearly flagged at the bottom.")
