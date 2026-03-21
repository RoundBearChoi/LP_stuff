import pandas as pd
from pathlib import Path
from typing import Optional, List
import matplotlib.pyplot as plt


class CointegrationDataProcessor:
    """
    Updated workflow (your exact request – March 2026):
    1. Loads full CSV
    2. Overlap filter (80% of global max) → self.filtered_df
    3. Strong cointegration filter → self.strong_df
    4. Plot half-life distribution (PNG created FIRST)
    5. Remove pairs outside chosen lower/upper percentiles
    6. Export cleaned CSV (NOW LAST)
    """

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.df: Optional[pd.DataFrame] = None
        self.filtered_df: Optional[pd.DataFrame] = None
        self.strong_df: Optional[pd.DataFrame] = None
        self.max_overlap_hours: Optional[int] = None
        self.threshold_hours: Optional[float] = None
        self._load_data()
        self._filter_by_overlap(percentage=0.8)

    def _load_data(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} pairs from '{self.csv_path.name}'")
        print(f"   Columns: {list(self.df.columns)}")
        print(f"   Date range example: {self.df['overlap_start'].min()} → {self.df['overlap_end'].max()}\n")

    def _filter_by_overlap(self, percentage: float = 0.8) -> None:
        if self.df is None:
            raise ValueError("Data not loaded yet.")

        self.max_overlap_hours = int(self.df['overlap_hours'].max())
        self.threshold_hours = percentage * self.max_overlap_hours

        self.filtered_df = self.df[self.df['overlap_hours'] >= self.threshold_hours].copy()

        kept_pct = len(self.filtered_df) / len(self.df) * 100
        removed = len(self.df) - len(self.filtered_df)

        print(f"🔍 Max overlap_hours in dataset : {self.max_overlap_hours:,} hours")
        print(f"📏 {percentage*100:.0f}% threshold               : {self.threshold_hours:,.0f} hours")
        print(f"✅ Kept {len(self.filtered_df):,} pairs ({kept_pct:.1f}%)")
        print(f"❌ Removed {removed:,} pairs with insufficient overlap\n")

    def filter_strong_cointegrations(self) -> None:
        if self.filtered_df is None:
            raise ValueError("Overlap-filtered data must be ready first (run __init__).")

        self.strong_df = self.filtered_df[
            self.filtered_df['verdict'].str.contains('STRONG', na=False)
        ].copy()

        kept = len(self.strong_df)
        total = len(self.filtered_df)
        kept_pct = (kept / total * 100) if total > 0 else 0

        print(f"🔥 STRONG COINTEGRATION FILTER APPLIED")
        print(f"✅ Kept {kept:,} STRONG pairs ({kept_pct:.1f}% of overlap-filtered data)")
        print(f"❌ Removed {total - kept:,} non-strong pairs\n")

    # ===================================================================
    # NEW: Percentile trimming (exactly matches the chart you just saw)
    # ===================================================================
    def filter_by_half_life_percentiles(self, lower_percentile: float = 10.0, upper_percentile: float = 90.0) -> None:
        """Remove every pair whose half_life_days is outside the chosen percentiles.
        Called AFTER plot_half_life_distribution() so the exported CSV matches the chart."""
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        if df is None or len(df) == 0:
            print("❌ No data available for percentile filtering.")
            return

        lower_val = df['half_life_days'].quantile(lower_percentile / 100)
        upper_val = df['half_life_days'].quantile(upper_percentile / 100)

        mask = (df['half_life_days'] >= lower_val) & (df['half_life_days'] <= upper_val)
        kept_df = df[mask].copy()

        kept_pct = len(kept_df) / len(df) * 100
        removed = len(df) - len(kept_df)

        print(f"✂️ HALF-LIFE PERCENTILE TRIM APPLIED ({lower_percentile:.0f}th – {upper_percentile:.0f}th)")
        print(f"   Range kept : {lower_val:.2f} → {upper_val:.2f} days")
        print(f"✅ Kept {len(kept_df):,} pairs ({kept_pct:.1f}%)")
        print(f"❌ Removed {removed:,} extreme pairs\n")

        # Update the working dataframe
        if self.strong_df is not None:
            self.strong_df = kept_df
        else:
            self.filtered_df = kept_df

    def summary(self) -> None:
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        if df is None:
            print("No data yet.")
            return

        title = "STRONG COINTEGRATED PAIRS SUMMARY (overlap + strong + percentile trim)"
        if self.strong_df is None:
            title = "OVERLAP-FILTERED SUMMARY"

        print(f"📊 {title}")
        print("=" * 70)
        print(df[['overlap_hours', 'hourly_pearson', 'daily_pearson',
                  'abs_corr', 'cointegration_pvalue', 
                  'half_life_days']].describe().round(4))
        print(f"\nTotal pairs kept: {len(df):,}")

    def top_strong_cointegrations(self, n: int = 10, min_half_life_days: float = 0.01) -> pd.DataFrame:
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        if df is None:
            return pd.DataFrame()
        
        return (df[
            (df['half_life_days'] >= min_half_life_days)
        ].sort_values('half_life_days', ascending=True)
         .head(n)[['pair', 'symbol1', 'symbol2', 'overlap_hours', 
                   'hourly_pearson', 'cointegration_pvalue', 
                   'half_life_days', 'beta']])

    def export_filtered(self, output_path: Optional[str] = None) -> str:
        if self.strong_df is not None:
            df_to_export = self.strong_df
            data_type = "strong + long-overlap + percentile-trimmed"
        elif self.filtered_df is not None:
            df_to_export = self.filtered_df
            data_type = "overlap-only"
        else:
            raise ValueError("No data to export.")

        if output_path is None:
            output_path = self.csv_path.with_name(f"cleanedup_{self.csv_path.name}")

        df_to_export.to_csv(output_path, index=False)
        print(f"💾 Exported {data_type} data → {output_path}")
        return str(output_path)

    def get_pairs_list(self) -> List[str]:
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        return df['pair'].tolist() if df is not None else []

    def plot_half_life_distribution(
        self, 
        output_png: Optional[str] = None, 
        log_scale: bool = False,
        lower_percentile: float = 10.0,
        upper_percentile: float = 90.0
    ) -> str:
        # (Unchanged – exactly the same beautiful chart you already had)
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        if df is None or len(df) == 0:
            print("❌ No data available for plotting.")
            return ""

        half_lives = df['half_life_days'].dropna().sort_values().reset_index(drop=True)
        if len(half_lives) == 0:
            print("❌ No valid half-life data found.")
            return ""

        n = len(half_lives)
        median_hl = half_lives.median()

        lower_percentile = max(0.0, min(100.0, float(lower_percentile)))
        upper_percentile = max(0.0, min(100.0, float(upper_percentile)))

        rank_lower = max(0, min(n-1, int(n * lower_percentile / 100)))
        rank_50    = int(n * 0.50)
        rank_upper = max(0, min(n-1, int(n * upper_percentile / 100)))

        hl_lower = half_lives.iloc[rank_lower]
        hl_upper = half_lives.iloc[rank_upper]

        plt.figure(figsize=(16, 11.0))
        plt.plot(half_lives.index, half_lives.values, color='royalblue', linewidth=1.8, alpha=0.85, label='Half-life (days)')
        plt.axvline(x=rank_lower, color='orange', linestyle='--', linewidth=2.2, alpha=0.85, label=f'{lower_percentile:.0f}th percentile')
        plt.axvline(x=rank_50, color='crimson', linestyle='--', linewidth=2.8, alpha=0.95, label='Median')
        plt.axvline(x=rank_upper, color='purple', linestyle='--', linewidth=2.2, alpha=0.85, label=f'{upper_percentile:.0f}th percentile')
        plt.axhline(y=median_hl, color='crimson', linestyle=':', linewidth=1.5, alpha=0.6)

        title = "Half-Life Distribution – Strong Cointegrated Pairs\n(Sorted: Lowest → Highest)"
        if self.strong_df is None:
            title = "Half-Life Distribution – Overlap-Filtered Pairs\n(Sorted: Lowest → Highest)"
            
        plt.title(title, fontsize=15, pad=20)
        plt.xlabel("Rank (1 = shortest half-life)", fontsize=12)
        plt.ylabel("Half-Life (days)" + (" – Log Scale" if log_scale else ""), fontsize=12)
        if log_scale:
            plt.yscale('log')
        plt.grid(True, alpha=0.35, linestyle='--')
        plt.legend(fontsize=11, loc='upper right', framealpha=0.92, fancybox=True)

        stats_text = f"""Total pairs: {n:,}
{lower_percentile:.0f}th percentile: {hl_lower:.2f} days (rank {rank_lower:,})
Median: {median_hl:.2f} days (rank {rank_50:,})
{upper_percentile:.0f}th percentile: {hl_upper:.2f} days (rank {rank_upper:,})
Mean: {half_lives.mean():.2f} days | Min: {half_lives.min():.2f} | Max: {half_lives.max():.2f} days"""

        plt.figtext(0.5, 0.038, stats_text, ha='center', va='center', 
                    fontsize=10.2, fontfamily='monospace',
                    bbox=dict(boxstyle="round,pad=0.85", facecolor="white", alpha=0.96, edgecolor='gray'))

        plt.subplots_adjust(bottom=0.245)

        if output_png is None:
            base = self.csv_path.stem
            suffix = "_strong" if self.strong_df is not None else ""
            output_png = self.csv_path.parent / f"{base}_half_life_distribution{suffix}.png"

        plt.savefig(output_png, dpi=165, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"📊 Chart saved with {lower_percentile:.0f}th / Median / {upper_percentile:.0f}th percentiles")
        print(f"   → {output_png}")
        print(f"   Pairs plotted: {n:,}")
        return str(output_png)


# =======================================================================
# NEW WORKFLOW (exactly what you asked for)
# =======================================================================
if __name__ == "__main__":
    processor = CointegrationDataProcessor(
        "all_pairs_cointegration_correlation_johansen_one_direction_18m_top44253.csv"
    )
    
    processor.filter_strong_cointegrations()
    
    print("\n" + "="*80)
    print("🎨 STEP 1: Generating half-life distribution chart...")

    # Change these two numbers if you want a different trim range
    LOWER_P = 10
    UPPER_P = 90

    processor.plot_half_life_distribution(lower_percentile=LOWER_P, upper_percentile=UPPER_P)
    
    print("\n✂️ STEP 2: Removing pairs outside the percentiles shown in the chart...")
    processor.filter_by_half_life_percentiles(lower_percentile=LOWER_P, upper_percentile=UPPER_P)
    
    print("\n💾 STEP 3: Exporting final cleaned CSV (now last)...")
    processor.export_filtered()

    print("\n🔝 Top 5 after trimming:")
    top = processor.top_strong_cointegrations(n=5)
    print(top.to_string(index=False))
    
    processor.summary()
    print("="*80)
