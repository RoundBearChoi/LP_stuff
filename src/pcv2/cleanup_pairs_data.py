import pandas as pd
from pathlib import Path
from typing import Optional, List
import matplotlib.pyplot as plt   # NEW: required for the final chart


class CointegrationDataProcessor:
    """
    Updated for your exact request:
    1. Loads full CSV
    2. Overlap filter (80% of global max) → self.filtered_df
    3. NEW SEPARATE FUNCTION: strong cointegration filter → self.strong_df
    4. NEW FINAL FUNCTION: plot_half_life_distribution() ← now with vertical 10/50/90 lines
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
        print(f"📏 80% threshold                 : {self.threshold_hours:,.0f} hours")
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

    def summary(self) -> None:
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
        df = self.strong_df if self.strong_df is not None else self.filtered_df
        return df['pair'].tolist() if df is not None else []

    # ===================================================================
    # FIXED VERSION – no top-left overlap (legend upper right + stats box bottom left)
    # ===================================================================
    def plot_half_life_distribution(self, output_png: Optional[str] = None, log_scale: bool = False) -> str:
        """
        FIXED VERSION – no top-left overlap
        - Legend moved to upper right
        - Stats box moved to bottom left (flat area)
        - Slightly shorter legend labels + cleaner stats formatting
        - Wider figure + higher DPI for better readability
        """
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

        # Percentile ranks
        rank_10 = int(n * 0.10)
        rank_50 = int(n * 0.50)
        rank_90 = int(n * 0.90)

        hl_10 = half_lives.iloc[rank_10]
        hl_90 = half_lives.iloc[rank_90]

        plt.figure(figsize=(15.5, 8.5))  # ← Slightly wider for breathing room
        
        # Main sorted line
        plt.plot(half_lives.index, half_lives.values, 
                 color='royalblue', linewidth=1.8, alpha=0.85, 
                 label='Half-life (days)')

        # Vertical lines (shorter labels – ranks moved to stats box)
        plt.axvline(x=rank_10, color='orange', linestyle='--', linewidth=2.2, alpha=0.85,
                    label='10th percentile')
        plt.axvline(x=rank_50, color='crimson', linestyle='--', linewidth=2.8, alpha=0.95,
                    label='Median')
        plt.axvline(x=rank_90, color='purple', linestyle='--', linewidth=2.2, alpha=0.85,
                    label='90th percentile')

        # Faint median horizontal reference
        plt.axhline(y=median_hl, color='crimson', linestyle=':', linewidth=1.5, alpha=0.6)

        title = "Half-Life Distribution – Strong Cointegrated Pairs\n(Sorted: Lowest → Highest)"
        if self.strong_df is None:
            title = "Half-Life Distribution – Overlap-Filtered Pairs\n(Sorted: Lowest → Highest)"
            
        plt.title(title, fontsize=15, pad=20)
        plt.xlabel("Rank (1 = shortest half-life)", fontsize=12)
        plt.ylabel("Half-Life (days)", fontsize=12)
        
        if log_scale:
            plt.yscale('log')
            plt.ylabel("Half-Life (days) – Log Scale", fontsize=12)
            
        plt.grid(True, alpha=0.35, linestyle='--')
        
        # === CLEAN LEGEND (upper right) ===
        plt.legend(fontsize=11, loc='upper right', framealpha=0.92, fancybox=True)

        # === STATS BOX (bottom left – perfect empty space) ===
        stats_text = (
            f"Total pairs : {n:,}\n"
            f"10th percentile : {hl_10:.2f} days (rank {rank_10:,})\n"
            f"Median          : {median_hl:.2f} days (rank {rank_50:,})\n"
            f"90th percentile : {hl_90:.2f} days (rank {rank_90:,})\n"
            f"Mean: {half_lives.mean():.2f} | Min: {half_lives.min():.2f} | Max: {half_lives.max():.2f}"
        )

        plt.text(0.02, 0.04, stats_text, transform=plt.gca().transAxes,
                 bbox=dict(boxstyle="round,pad=0.8", facecolor="white", alpha=0.95, edgecolor='gray'),
                 verticalalignment='bottom', fontsize=10.1, fontfamily='monospace')

        # Default filename
        if output_png is None:
            base = self.csv_path.stem
            suffix = "_strong" if self.strong_df is not None else ""
            output_png = self.csv_path.parent / f"{base}_half_life_distribution{suffix}.png"

        plt.savefig(output_png, dpi=160, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"📊 Fixed half-life distribution chart saved:")
        print(f"   → {output_png}")
        print(f"   Pairs plotted: {n:,}")
        print(f"   10th–90th range : {hl_10:.2f} → {hl_90:.2f} days")
        print(f"   Median          : {median_hl:.2f} days (rank {rank_50:,})")
        
        return str(output_png)


# =======================================================================
# Example usage (run this script directly)
# =======================================================================
if __name__ == "__main__":
    processor = CointegrationDataProcessor(
        "all_pairs_cointegration_correlation_johansen_one_direction_18m_top44253.csv"
    )
    
    processor.summary()
    
    # === STRONG FILTER (as before) ===
    processor.filter_strong_cointegrations()
    
    print("\n🔝 Top 5 strongest cointegrations (shortest half-life):")
    top = processor.top_strong_cointegrations(n=5)
    print(top.to_string(index=False))
    
    processor.export_filtered()

    # === FINAL PROCESS: half-life chart with 10/50/90 vertical lines ===
    print("\n" + "="*80)
    print("🎨 FINAL PROCESS: Generating sorted half-life distribution chart...")
    processor.plot_half_life_distribution()
    print("="*80)
