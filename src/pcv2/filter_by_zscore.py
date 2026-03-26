import pandas as pd
from pathlib import Path
from typing import Optional, List
import matplotlib.pyplot as plt
import numpy as np
from cointegration_engine import compute_cointegration
from config import DEFAULT_CSV_FILE, DEFAULT_COINTEGRATION_METHOD


# ====================== CONFIG (change these!) ======================
INPUT_CSV: str = "filtered_by_stability_johansen_one_direction_18m_top42778.csv"

Z_UPPER_THRESHOLD: float = 1.0
Z_LOWER_THRESHOLD: float = -1.0
REVERT_CONFIRM_LEVEL: float = 0.25          # must revert past this level to count as completed round-trip

# Lookback (matches stability script)
MAX_MONTHS_FOR_ZSCORE: int = 18

# Plot & output
PLOT_DISTRIBUTION: bool = True
# =====================================================================


class ZscoreDataProcessor:
    """
    Post-stability processor (March 2026):
    1. Loads the stability-filtered CSV
    2. Computes balanced z-score reversion count (completed round-trips at ±2)
    3. Adds several useful columns (up/down/total/signals_per_year)
    4. Plots distribution (PNG created)
    5. Sorts: balanced_reversion_count DESC → stability DESC → half_life ASC
    6. Exports final CSV (noise still at bottom)

    Output filename format:
    - CSV:  filtered_by_zscore_johansen_one_direction_18m_top42778.csv
    - PNG:  filtered_by_zscore_johansen_one_direction_18m_top42778_reversion_distribution.png
    """

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.df: Optional[pd.DataFrame] = None
        self._load_data()

    def _load_data(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} pairs from stability-filtered CSV '{self.csv_path.name}'")
        print(f"   Columns: {list(self.df.columns)}\n")

    def add_zscore_reversion_metrics(self) -> None:
        if self.df is None or len(self.df) == 0:
            print("❌ No data available.")
            return

        print(f"\n🔬 COMPUTING Z-SCORE REVERSION METRICS (±{Z_UPPER_THRESHOLD} → revert past ±{REVERT_CONFIRM_LEVEL})")
        print("   This answers: 'how many completed volatility-harvest rebalance opportunities per pair?'")
        print(f"   Using last {MAX_MONTHS_FOR_ZSCORE} months of price data (consistent with stability)")

        # Reuse same price loading logic as stability script for speed
        price_df = pd.read_csv(DEFAULT_CSV_FILE, parse_dates=['datetime'])
        end_date = price_df['datetime'].max()
        days_back = int(MAX_MONTHS_FOR_ZSCORE * 30.437 * 1.1)
        price_df = price_df[price_df['datetime'] >= (end_date - pd.Timedelta(days=days_back))].copy()
        print(f"   → Loaded last {MAX_MONTHS_FOR_ZSCORE} months: {len(price_df):,} hourly bars")

        up_revs = []
        down_revs = []
        n_pairs = len(self.df)

        for i, row in enumerate(self.df.itertuples(index=False), 1):
            if i % max(10, n_pairs // 8) == 0:
                print(f"   Progress: {i:,}/{n_pairs:,} pairs processed")

            sym1, sym2 = row.symbol1, row.symbol2

            pair_data = price_df[price_df['symbol'].isin([sym1, sym2])].copy()
            if len(pair_data) < 500:
                up_revs.append(0)
                down_revs.append(0)
                continue

            pivot = pair_data.pivot(index='datetime', columns='symbol', values='close').dropna()
            if sym1 not in pivot.columns or sym2 not in pivot.columns or len(pivot) < 500:
                up_revs.append(0)
                down_revs.append(0)
                continue

            p1 = pivot[sym1]
            p2 = pivot[sym2]

            # Full-period cointegration (uses exact same engine as your original pipeline)
            try:
                result = compute_cointegration(p1, p2, method=DEFAULT_COINTEGRATION_METHOD)
                
                # Robust hedge_ratio extraction (works for Johansen or other methods)
                if hasattr(result, 'hedge_ratio'):
                    hedge = float(result.hedge_ratio)
                elif hasattr(result, 'beta'):
                    hedge = float(result.beta[0]) if isinstance(result.beta, (list, np.ndarray)) else float(result.beta)
                else:
                    hedge = 1.0  # fallback
                
                # Cointegrated spread (log prices standard for multiplicative assets)
                spread = np.log(p1) - hedge * np.log(p2)
                zscore = (spread - spread.mean()) / spread.std(ddof=0)
                
                # Count completed round-trips
                up = 0
                down = 0
                idx = 0
                n = len(zscore)
                while idx < n:
                    z = zscore.iloc[idx]
                    if z > Z_UPPER_THRESHOLD:
                        # look for reversion
                        for j in range(idx + 1, n):
                            if zscore.iloc[j] < REVERT_CONFIRM_LEVEL:
                                up += 1
                                idx = j
                                break
                        else:
                            idx = n
                    elif z < Z_LOWER_THRESHOLD:
                        for j in range(idx + 1, n):
                            if zscore.iloc[j] > -REVERT_CONFIRM_LEVEL:
                                down += 1
                                idx = j
                                break
                        else:
                            idx = n
                    else:
                        idx += 1
                        
                up_revs.append(up)
                down_revs.append(down)
            except Exception:
                up_revs.append(0)
                down_revs.append(0)

        self.df = self.df.copy()
        self.df['zscore_up_reversions'] = up_revs
        self.df['zscore_down_reversions'] = down_revs
        self.df['balanced_reversion_count'] = [min(u, d) for u, d in zip(up_revs, down_revs)]
        self.df['total_reversions'] = [u + d for u, d in zip(up_revs, down_revs)]

        # Normalize to frequency (fair across different overlap lengths)
        if 'overlap_hours' in self.df.columns:
            self.df['data_years'] = self.df['overlap_hours'] / (24 * 365.25)
            self.df['signals_per_year'] = self.df['total_reversions'] / self.df['data_years'].replace(0, np.nan)

        mean_score = self.df['balanced_reversion_count'].mean()
        print(f"✅ Z-score metrics added! Mean balanced reversions: {mean_score:.2f}")
        print(f"   Columns added: balanced_reversion_count, total_reversions, signals_per_year\n")

    def plot_reversion_distribution(self, output_png: Optional[str] = None) -> str:
        if 'balanced_reversion_count' not in self.df.columns or len(self.df) == 0:
            print("❌ No z-score data to plot.")
            return ""

        counts = self.df['balanced_reversion_count'].dropna().sort_values().reset_index(drop=True)
        n = len(counts)

        plt.figure(figsize=(16, 10))
        plt.plot(counts.index, counts.values, color='teal', linewidth=1.8, alpha=0.85, label='Balanced reversion count')
        plt.axhline(y=counts.median(), color='crimson', linestyle='--', linewidth=2.5, label='Median')
        plt.title("Z-Score Reversion Opportunities Distribution\n(Sorted: Lowest → Highest)", fontsize=15, pad=20)
        plt.xlabel("Rank (1 = fewest opportunities)", fontsize=12)
        plt.ylabel("Balanced Reversion Count (min(up, down))", fontsize=12)
        plt.grid(True, alpha=0.35, linestyle='--')
        plt.legend(fontsize=11)

        stats_text = f"""Total pairs: {n:,}
Median: {counts.median():.1f}
Mean: {counts.mean():.2f} | Max: {counts.max():.0f} | Min: {counts.min():.0f}
(Each count = completed trigger-based rebalance opportunity)"""

        plt.figtext(0.5, 0.04, stats_text, ha='center', va='center', fontsize=10.5, 
                    fontfamily='monospace', bbox=dict(boxstyle="round,pad=0.8", facecolor="white", alpha=0.96))

        plt.subplots_adjust(bottom=0.22)

        if output_png is None:
            stem = self.csv_path.stem.replace("filtered_by_stability_", "filtered_by_zscore_")
            output_png = self.csv_path.parent / f"{stem}_reversion_distribution.png"

        plt.savefig(output_png, dpi=165, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"📊 Reversion distribution chart saved → {output_png}")
        print(f"   Pairs plotted: {n:,}")
        return str(output_png)

    def export_filtered(self, output_path: Optional[str] = None) -> str:
        if self.df is None:
            raise ValueError("No data to export.")

        df_to_export = self.df.copy()

        # Multi-key sort (best opportunities on top, noise at bottom)
        if {'balanced_reversion_count', 'cointegration_stability_score', 'half_life_days', 'noise'}.issubset(df_to_export.columns):
            df_to_export = df_to_export.sort_values(
                by=['noise', 'balanced_reversion_count', 'cointegration_stability_score', 'half_life_days'],
                ascending=[True, False, False, True]
            ).reset_index(drop=True)
            print("   📋 Sorted by: noise (False first) → balanced_reversion_count DESC → stability DESC → half_life ASC")

        if output_path is None:
            stem = self.csv_path.stem
            if stem.startswith("filtered_by_stability_"):
                new_stem = stem.replace("filtered_by_stability_", "filtered_by_zscore_")
            else:
                new_stem = f"filtered_by_zscore_{stem}"
            output_path = self.csv_path.with_name(f"{new_stem}.csv")

        df_to_export.to_csv(output_path, index=False)
        print(f"💾 Exported z-score-ranked pairs → {output_path}")
        
        if len(df_to_export) > 0:
            best = df_to_export.iloc[0]
            print(f"   🏆 Top pair: {best['pair']} | balanced_reversions={best['balanced_reversion_count']} "
                  f"| stability={best.get('cointegration_stability_score', 'N/A'):.4f} "
                  f"| half_life={best['half_life_days']:.1f} days")

        return str(output_path)

    def summary(self) -> None:
        if self.df is None:
            return
        print("\n📊 Z-SCORE RANKING SUMMARY")
        print("=" * 70)
        cols = ['balanced_reversion_count', 'total_reversions', 'signals_per_year',
                'cointegration_stability_score', 'half_life_days', 'noise']
        cols = [c for c in cols if c in self.df.columns]
        print(self.df[cols].describe().round(3))
        print(f"\nTotal pairs: {len(self.df):,}")
        if 'noise' in self.df.columns:
            print(f"   Clean (noise=False): {(self.df['noise'] == False).sum():,}")
            print(f"   Noise  (noise=True) : {(self.df['noise'] == True).sum():,}")


# =======================================================================
# MAIN EXECUTION
# =======================================================================
if __name__ == "__main__":
    processor = ZscoreDataProcessor(INPUT_CSV)
    
    print("\n" + "="*80)
    print("🔬 STEP 1: Computing z-score reversion metrics...")
    processor.add_zscore_reversion_metrics()
    
    if PLOT_DISTRIBUTION:
        print("\n🎨 STEP 2: Generating reversion opportunities chart...")
        processor.plot_reversion_distribution()
    
    print("\n💾 STEP 3: Exporting final z-score-ranked CSV...")
    processor.export_filtered()
    
    processor.summary()
    print("="*80)
    print("✅ filter_by_zscore.py finished! Ready for trading.")
