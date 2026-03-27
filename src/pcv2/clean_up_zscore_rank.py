import pandas as pd
import numpy as np
import os
from pathlib import Path

# ==================== CONFIG SECTION ====================
# Edit these variables to customize the script without changing the core logic.
# All paths are relative to the script's location unless you use absolute paths.

# Input CSV file (must contain the columns listed below)
INPUT_FILE = "filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv"

# Percentile threshold for "balanced_reversion_count"
# Default = 80 → we keep only pairs at or above the 80th percentile
PERCENTILE_THRESHOLD = 80.0

# Column names – change only if your CSV uses different headers
BALANCED_REVERSION_COUNT_COL = "balanced_reversion_count"
REVERSION_CONSISTENCY_SCORE_COL = "reversion_consistency_score"
UNIQUE_PAIR_IDENTIFIER_COL = "pair"          # Used to merge ranks back safely

# Output filename format (as requested: cleaned_up_zscore_ranking_whatever.csv)
# "whatever" is automatically replaced by the input filename (without .csv extension)
# Example: cleaned_up_zscore_ranking_filtered_by_zscore_filtered_by_volume_johansen_one_direction_18m_top42778.csv
OUTPUT_PREFIX = "cleaned_up_zscore_ranking"

# Sorting direction for consistency ranking
# Higher consistency score = better → we sort descending (False)
SORT_CONSISTENCY_ASCENDING = False

# Optional: add extra debug prints (True = more verbose output)
DEBUG = True

# ======================================================

def main():
    print("=== clean_up_zscore_rank.py started ===")
    print(f"Input file : {INPUT_FILE}")
    print(f"Target percentile : {PERCENTILE_THRESHOLD}th of '{BALANCED_REVERSION_COUNT_COL}'")
    print(f"Ranking column : '{REVERSION_CONSISTENCY_SCORE_COL}' (higher = better)")

    # 1. Load the CSV
    if not Path(INPUT_FILE).exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_FILE}")
    
    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df):,} rows and {len(df.columns)} columns.")

    # 2. Validate required columns exist
    required_cols = [
        BALANCED_REVERSION_COUNT_COL,
        REVERSION_CONSISTENCY_SCORE_COL,
        UNIQUE_PAIR_IDENTIFIER_COL
    ]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. "
                         f"Available columns: {list(df.columns)}")

    # 3. Calculate the percentile threshold
    threshold = df[BALANCED_REVERSION_COUNT_COL].quantile(PERCENTILE_THRESHOLD / 100.0)
    print(f"{PERCENTILE_THRESHOLD}th percentile value = {threshold:,.2f}")

    # 4. Mark every row with its category
    df["reversion_category"] = np.where(
        df[BALANCED_REVERSION_COUNT_COL] >= threshold,
        "top_80_percentile",
        "low_reversion_count"
    )

    # 5. Rank ONLY the top 80th percentile rows by consistency score
    #    All other rows receive NaN (no calculations performed, as requested)
    df["rank_within_top"] = pd.NA   # explicit NA for low-reversion rows

    top_mask = df["reversion_category"] == "top_80_percentile"
    top_count = top_mask.sum()

    if top_count > 0:
        top_df = df[top_mask].copy()

        # Sort by consistency (higher = better)
        top_df = top_df.sort_values(
            by=REVERSION_CONSISTENCY_SCORE_COL,
            ascending=SORT_CONSISTENCY_ASCENDING
        ).reset_index(drop=True)

        # Assign dense ranks starting at 1
        top_df["rank_within_top"] = top_df.index + 1

        # Merge the ranks back into the original DataFrame using the unique pair key
        rank_map = dict(zip(top_df[UNIQUE_PAIR_IDENTIFIER_COL], top_df["rank_within_top"]))
        df["rank_within_top"] = df[UNIQUE_PAIR_IDENTIFIER_COL].map(rank_map)

        print(f"✅ Ranked {top_count:,} top pairs (1 = highest consistency)")
    else:
        print("⚠️  No pairs reached the 80th percentile – all marked low_reversion_count")

    # 6. (Optional) Nice output ordering: top pairs first (by rank), then low-reversion rows
    df = df.sort_values(
        by=["reversion_category", "rank_within_top"],
        ascending=[False, True],   # top_80 first, then rank 1,2,3…
        na_position="last"
    )

    # 7. Generate output filename
    input_stem = Path(INPUT_FILE).stem
    OUTPUT_FILE = f"{OUTPUT_PREFIX}_{input_stem}.csv"
    print(f"Output will be saved as: {OUTPUT_FILE}")

    # 8. Save the enriched CSV (all original columns + 2 new ones)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Saved {len(df):,} rows to {OUTPUT_FILE}")

    # 9. Summary statistics (always shown)
    summary = df["reversion_category"].value_counts().to_dict()
    print("\n=== FINAL SUMMARY ===")
    print(f"Top 80th percentile pairs : {summary.get('top_80_percentile', 0):,}")
    print(f"Low reversion count pairs : {summary.get('low_reversion_count', 0):,}")
    print(f"Total pairs processed     : {len(df):,}")

    if DEBUG:
        print("\nPreview of first 5 rows (with new columns):")
        print(df.head(5)[[UNIQUE_PAIR_IDENTIFIER_COL,
                          BALANCED_REVERSION_COUNT_COL,
                          REVERSION_CONSISTENCY_SCORE_COL,
                          "reversion_category",
                          "rank_within_top"]].to_string(index=False))

    print("\n=== Script finished successfully ===")


if __name__ == "__main__":
    main()
