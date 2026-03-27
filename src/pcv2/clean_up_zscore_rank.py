#!/usr/bin/env python3
"""
clean_up_zscore_rank.py

This script processes the filtered cointegration pairs CSV and creates a clean, ranked output
specifically for z-score mean-reversion trading strategies.

WHAT IT DOES:
1. Loads the full dataset (filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv).
2. Identifies the TOP X% of pairs based on 'balanced_reversion_count' (configurable).
3. Sorts ONLY those top pairs by 'balanced_reversion_consistency_score'.
4. Marks ALL remaining pairs with the flag 'low balanced reversion count' and moves them to the bottom.
5. Adds two new helpful columns: 'rank_category' and 'final_rank'.
6. Saves everything to a new CSV with a filename that automatically reflects the chosen percentile.

The script is fully configurable at the top.
"""

import pandas as pd

# ==================== CONFIG SECTION ====================
# ←←← CHANGE THESE VARIABLES AS NEEDED →→→

# File paths
INPUT_FILE = "filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv"

# <<< NEW: Dynamic output filename that matches the percentile >>>
TOP_PERCENTILE = 40                     # Top X% by balanced_reversion_count
OUTPUT_FILE = f"zscore_ranked_balanced_reversion_top{TOP_PERCENTILE}.csv"

# Ranking rules
SORT_BY_COLUMN = "balanced_reversion_consistency_score"
SORT_ASCENDING = False                  # False = highest consistency first (recommended)

# Column names
BALANCED_COUNT_COL = "balanced_reversion_count"
BALANCED_CONSISTENCY_COL = "balanced_reversion_consistency_score"

# Optional: extra columns you want to keep at the front
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

# Sort the high-quality group by consistency score
high_df = high_df.sort_values(by=SORT_BY_COLUMN, ascending=SORT_ASCENDING)

# Mark the groups clearly
high_df["rank_category"] = "high_balanced_reversion"
low_df["rank_category"] = "low balanced reversion count"

# Combine: high-quality first, then low-quality at the bottom
final_df = pd.concat([high_df, low_df], ignore_index=True)

# Add an overall rank column
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
