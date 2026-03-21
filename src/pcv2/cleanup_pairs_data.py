import pandas as pd
from pathlib import Path
from typing import Optional, List

class CointegrationDataProcessor:
    """
    Updated for your exact request:
    1. Loads full CSV
    2. Overlap filter (80% of global max) → self.filtered_df
    3. NEW SEPARATE FUNCTION: strong cointegration filter → self.strong_df
    
    The exported "cleanedup_" file now contains ONLY strong cointegrations
    that survived the overlap filter. Everything else is untouched.
    """

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.df: Optional[pd.DataFrame] = None
        self.filtered_df: Optional[pd.DataFrame] = None          # overlap only
        self.strong_df: Optional[pd.DataFrame] = None            # strong only (new)
        self.max_overlap_hours: Optional[int] = None
        self.threshold_hours: Optional[float] = None
        self._load_data()
        self._filter_by_overlap(percentage=0.8)

    def _load_data(self) -> None:
        """Internal: load the raw CSV and give immediate feedback."""
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} pairs from '{self.csv_path.name}'")
        print(f"   Columns: {list(self.df.columns)}")
        print(f"   Date range example: {self.df['overlap_start'].min()} → {self.df['overlap_end'].max()}\n")

    def _filter_by_overlap(self, percentage: float = 0.8) -> None:
        """
        Core overlap filter (unchanged from your original request).
        """
        if self.df is None:
            raise ValueError("Data not loaded yet.")

        self.max_overlap_hours = int(self.df['overlap_hours'].max())
        self.threshold_hours = percentage * self.max_overlap_hours

        self.filtered_df = self.df[self.df['overlap_hours'] >= self.threshold_hours].copy()

        kept_pct = len(self.filtered_df) / len(self.df) * 100
        removed = len(self.df) - len(self.filtered_df)

        print(f"🔍 Max overlap_hours in dataset : {self.max_overlap_hours:,} hours")
        print(f"📏 80% threshold                 : {self.threshold_hours:,.0f} hours")
        print(f"✅ Kept {len(self.filtered_df):,} pairs ({kept_pct:.1f}%)")
        print(f"❌ Removed {removed:,} pairs with insufficient overlap\n")

    # ===================================================================
    # NEW SEPARATE FUNCTION (exactly what you asked for)
    # ===================================================================

    def filter_strong_cointegrations(self) -> None:
        """
        SEPARATE FUNCTION as requested:
        Removes ALL entries that do NOT have strong cointegration
        (i.e. where 'verdict' does NOT contain 'STRONG').
        
        Applied on top of the overlap filter. Stores result in self.strong_df.
        """
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
    # Public methods – now prefer strong_df when available
    # ===================================================================

    def summary(self) -> None:
        """Rich overview — uses strong_df if you called the new filter."""
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        if df is None:
            print("No data yet.")
            return

        title = "STRONG COINTEGRATED PAIRS SUMMARY (both filters applied)"
        if self.strong_df is None:
            title = "OVERLAP-FILTERED SUMMARY (strong filter not yet applied)"

        print(f"📊 {title}")
        print("=" * 70)
        print(df[['overlap_hours', 'hourly_pearson', 'daily_pearson',
                  'abs_corr', 'cointegration_pvalue', 
                  'half_life_days']].describe().round(4))
        
        print(f"\nTotal pairs kept: {len(df):,}")

    def top_strong_cointegrations(self, n: int = 10, min_half_life_days: float = 0.01) -> pd.DataFrame:
        """
        Top n strongest (shortest half-life) — automatically uses strong_df.
        """
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
        """
        Exports the FINAL cleaned-up dataset.
        Priority: strong_df → filtered_df
        Default name (exactly as you wanted):
            cleanedup_all_pairs_cointegration_correlation_johansen_one_direction_18m_top44253.csv
        """
        if self.strong_df is not None:
            df_to_export = self.strong_df
            data_type = "strong + long-overlap"
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
        """List of surviving pair names (uses strong_df if available)."""
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        return df['pair'].tolist() if df is not None else []


# =======================================================================
# Example usage (run this script directly)
# =======================================================================
if __name__ == "__main__":
    processor = CointegrationDataProcessor(
        "all_pairs_cointegration_correlation_johansen_one_direction_18m_top44253.csv"
    )
    
    processor.summary()
    
    # === NEW SEPARATE STEP YOU REQUESTED ===
    processor.filter_strong_cointegrations()
    
    print("\n🔝 Top 5 strongest cointegrations (shortest half-life):")
    top = processor.top_strong_cointegrations(n=5)
    print(top.to_string(index=False))
    
    processor.export_filtered()
