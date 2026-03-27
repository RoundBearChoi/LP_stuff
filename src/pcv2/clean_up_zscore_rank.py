import pandas as pd
import numpy as np
import os
from pathlib import Path
import matplotlib.pyplot as plt

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

# Output filename format for the CSV
OUTPUT_PREFIX = "cleaned_up_zscore_ranking"

# Sorting direction for consistency ranking (higher consistency = better)
SORT_CONSISTENCY_ASCENDING = False

# ==================== NEW CHART CONFIG ====================
# DPI for the exported PNG (as requested)
CHART_DPI = 150

# Chart title (customizable)
CHART_TITLE = "Reversion Consistency Scores - Top 80th Percentile Pairs (by Balanced Reversion Count)"

# Output suffix for the chart PNG (same stem as CSV)
CHART_OUTPUT_SUFFIX = "_consistency_chart.png"

# Chart styling (feel free to tweak)
CHART_FIGSIZE = (12, 6)
CHART_LINE_COLOR = "navy"
CHART_MARKER_SIZE = 2
CHART_PERCENTILE_COLORS = {"20th": "red", "50th (median)": "green", "80th": "orange"}
CHART_PERCENTILE_LINestyle = "--"
CHART_SHOW_GRID = True

# Optional: add extra debug prints (True = more verbose output)
DEBUG = True

# ======================================================

def main():
    print("=== clean_up_zscore_rank.py started ===")
    print(f"Input file                  : {INPUT_FILE}")
    print(f"Target percentile           : {PERCENTILE_THRESHOLD}th of '{BALANCED_REVERSION_COUNT_COL}'")
    print(f"Ranking column              : '{REVERSION_CONSISTENCY_SCORE_COL}' (higher = better)")
    print(f"Chart DPI                   : {CHART_DPI}")
    print(f"Chart will be saved as      : {OUTPUT_PREFIX}_<input-stem>{CHART_OUTPUT_SUFFIX}")

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
    df["rank_within_top"] = pd.NA

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

        # Merge the ranks back
        rank_map = dict(zip(top_df[UNIQUE_PAIR_IDENTIFIER_COL], top_df["rank_within_top"]))
        df["rank_within_top"] = df[UNIQUE_PAIR_IDENTIFIER_COL].map(rank_map)

        print(f"✅ Ranked {top_count:,} top pairs (1 = highest consistency)")

        # === NEW: CALCULATE PERCENTILES FOR CHART ===
        consistency_series = top_df[REVERSION_CONSISTENCY_SCORE_COL]
        p20 = consistency_series.quantile(0.20)
        p50 = consistency_series.quantile(0.50)
        p80 = consistency_series.quantile(0.80)

        print(f"Top-group consistency percentiles:")
        print(f"   20th  : {p20:.4f}")
        print(f"   50th (median): {p50:.4f}")
        print(f"   80th  : {p80:.4f}")

    else:
        print("⚠️  No pairs reached the 80th percentile – all marked low_reversion_count")
        p20 = p50 = p80 = None

    # 6. Nice output ordering
    df = df.sort_values(
        by=["reversion_category", "rank_within_top"],
        ascending=[False, True],
        na_position="last"
    )

    # 7. Generate CSV filename
    input_stem = Path(INPUT_FILE).stem
    OUTPUT_CSV = f"{OUTPUT_PREFIX}_{input_stem}.csv"
    print(f"Output CSV will be saved as: {OUTPUT_CSV}")

    # 8. Save the enriched CSV
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"✅ Saved {len(df):,} rows to {OUTPUT_CSV}")

    # 9. NEW: Generate the PNG chart (only if we have top pairs)
    if top_count > 0:
        chart_file = f"{OUTPUT_PREFIX}_{input_stem}{CHART_OUTPUT_SUFFIX}"
        create_consistency_chart(
            top_df=top_df,
            p20=p20,
            p50=p50,
            p80=p80,
            chart_file=chart_file,
            dpi=CHART_DPI
        )
        print(f"✅ Exported chart to: {chart_file} (DPI={CHART_DPI})")

    # 10. Summary statistics
    summary = df["reversion_category"].value_counts().to_dict()
    print("\n=== FINAL SUMMARY ===")
    print(f"Top 80th percentile pairs : {summary.get('top_80_percentile', 0):,}")
    print(f"Low reversion count pairs : {summary.get('low_reversion_count', 0):,}")
    print(f"Total pairs processed     : {len(df):,}")

    if DEBUG and top_count > 0:
        print("\nPreview of first 5 top pairs (with new columns):")
        preview_cols = [UNIQUE_PAIR_IDENTIFIER_COL,
                        BALANCED_REVERSION_COUNT_COL,
                        REVERSION_CONSISTENCY_SCORE_COL,
                        "reversion_category",
                        "rank_within_top"]
        print(top_df.head(5)[preview_cols].to_string(index=False))

    print("\n=== Script finished successfully ===")


def create_consistency_chart(top_df, p20, p50, p80, chart_file, dpi):
    """
    Creates a clean, publication-ready chart showing:
    - All consistency scores of top 80th percentile pairs, ordered by rank (descending)
    - Horizontal dashed lines for 20th, 50th (median), and 80th percentiles
    - Saves as PNG at the requested DPI
    """
    plt.figure(figsize=CHART_FIGSIZE)
    ax = plt.gca()

    # X = rank (1 = best), Y = consistency score (already sorted descending)
    ranks = top_df["rank_within_top"]
    scores = top_df[REVERSION_CONSISTENCY_SCORE_COL]

    # Main line + markers
    ax.plot(ranks, scores,
            color=CHART_LINE_COLOR,
            linewidth=1.5,
            marker='o',
            markersize=CHART_MARKER_SIZE,
            label="Consistency Score (sorted descending)")

    # Percentile lines with labels
    if p20 is not None:
        ax.axhline(p20, color=CHART_PERCENTILE_COLORS["20th"], linestyle=CHART_PERCENTILE_LINestyle,
                   linewidth=1.5, label=f"20th percentile ({p20:.4f})")
    if p50 is not None:
        ax.axhline(p50, color=CHART_PERCENTILE_COLORS["50th (median)"], linestyle=CHART_PERCENTILE_LINestyle,
                   linewidth=1.5, label=f"Median / 50th percentile ({p50:.4f})")
    if p80 is not None:
        ax.axhline(p80, color=CHART_PERCENTILE_COLORS["80th"], linestyle=CHART_PERCENTILE_LINestyle,
                   linewidth=1.5, label=f"80th percentile ({p80:.4f})")

    # Styling
    ax.set_title(CHART_TITLE, fontsize=14, pad=20)
    ax.set_xlabel("Rank within Top 80th Percentile (1 = highest consistency)", fontsize=12)
    ax.set_ylabel("Reversion Consistency Score", fontsize=12)
    ax.grid(CHART_SHOW_GRID, alpha=0.3)
    ax.legend(loc="upper right", fontsize=10, frameon=True)

    # Optional: annotate the number of pairs
    ax.text(0.02, 0.95, f"N = {len(top_df):,} pairs",
            transform=ax.transAxes, fontsize=11,
            verticalalignment="top", bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))

    plt.tight_layout()

    # Save at exact DPI requested
    plt.savefig(chart_file, dpi=dpi, bbox_inches="tight")
    plt.close()  # free memory


if __name__ == "__main__":
    main()
