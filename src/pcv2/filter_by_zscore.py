import pandas as pd
from pathlib import Path
from typing import Optional
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

from cointegration_engine import compute_cointegration
from config import DEFAULT_CSV_FILE, DEFAULT_COINTEGRATION_METHOD

from get_zscore_reversion_metrics import compute_zscore_reversion_metrics


# ====================== CONFIG (change these!) ======================
INPUT_CSV: str = "filtered_by_volume_johansen_one_direction_18m_top42778.csv"

Z_UPPER_THRESHOLD: float = 1.5
Z_LOWER_THRESHOLD: float = -1.5
REVERT_CONFIRM_LEVEL: float = 0.5

MAX_MONTHS_FOR_ZSCORE: int = 18

PLOT_DISTRIBUTION: bool = True
# =====================================================================


class ZscoreDataProcessor:
    """
    Post-stability processor (March 2026) — now with volume prioritization
    AND reversion_frequency_consistency_score (temporal regularity of events).
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
        print("   Now also computing TEMPORAL FREQUENCY CONSISTENCY of reversions")
        print(f"   Using last {MAX_MONTHS_FOR_ZSCORE} months of price data")

        # Load price data ONCE
        price_df = pd.read_csv(DEFAULT_CSV_FILE, parse_dates=['datetime'])
        end_date = price_df['datetime'].max()
        days_back = int(MAX_MONTHS_FOR_ZSCORE * 30.437 * 1.1)
        price_df = price_df[price_df['datetime'] >= (end_date - pd.Timedelta(days=days_back))].copy()
        print(f"   → Loaded last {MAX_MONTHS_FOR_ZSCORE} months: {len(price_df):,} hourly bars\n")

        n_pairs = len(self.df)
        up_revs = []
        down_revs = []
        consistency_scores = []
        mean_intervals = []
        max_gaps = []

        for row in tqdm(self.df.itertuples(index=False), total=n_pairs,
                        desc="Computing z-score reversions + consistency", unit="pair", ncols=100):
            sym1, sym2 = row.symbol1, row.symbol2

            metrics = compute_zscore_reversion_metrics(
                sym1, sym2,
                price_df=price_df,
                z_upper=Z_UPPER_THRESHOLD,
                z_lower=Z_LOWER_THRESHOLD,
                revert_confirm=REVERT_CONFIRM_LEVEL,
                max_months=MAX_MONTHS_FOR_ZSCORE,
                verbose=False,
            )

            up = metrics['zscore_up_reversions']
            down = metrics['zscore_down_reversions']
            timestamps = metrics.get('reversion_timestamps', [])

            up_revs.append(up)
            down_revs.append(down)

            # ====================== NEW: FREQUENCY CONSISTENCY ======================
            if len(timestamps) >= 2:
                # Robust fix that works on ALL pandas versions (no warning, no TypeError)
                ts_clean = pd.to_datetime(timestamps).tz_localize(None)
                deltas = (np.diff(ts_clean.values) / np.timedelta64(1, 'D')).astype(float)  # exact days (fractional OK)
                mean_delta = np.mean(deltas)
                std_delta = np.std(deltas)
                cv = std_delta / mean_delta if mean_delta > 0 else 0.0
                score = 1 / (1 + cv)
                max_gap = float(np.max(deltas))
            else:
                score = 0.0
                mean_delta = np.nan
                max_gap = np.nan
            # =====================================================================

            consistency_scores.append(score)
            mean_intervals.append(mean_delta)
            max_gaps.append(max_gap)

        self.df = self.df.copy()
        self.df['zscore_up_reversions'] = up_revs
        self.df['zscore_down_reversions'] = down_revs
        self.df['balanced_reversion_count'] = [min(u, d) for u, d in zip(up_revs, down_revs)]
        self.df['total_reversions'] = [u + d for u, d in zip(up_revs, down_revs)]

        self.df['reversion_consistency_score'] = consistency_scores
        self.df['mean_reversion_interval_days'] = mean_intervals
        self.df['max_reversion_gap_days'] = max_gaps

        if 'overlap_hours' in self.df.columns:
            self.df['data_years'] = self.df['overlap_hours'] / (24 * 365.25)
            self.df['signals_per_year'] = self.df['total_reversions'] / self.df['data_years'].replace(0, np.nan)

        mean_balanced = self.df['balanced_reversion_count'].mean()
        mean_consistency = self.df['reversion_consistency_score'].mean()
        print(f"\n✅ Z-score metrics added! Mean balanced reversions: {mean_balanced:.2f}")
        print(f"   Mean consistency score: {mean_consistency:.3f}")
        print(f"   Columns added: balanced_reversion_count, total_reversions, reversion_consistency_score, "
              f"mean_reversion_interval_days, max_reversion_gap_days, signals_per_year\n")

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

        if 'volume_level' in df_to_export.columns:
            df_to_export['volume_priority'] = df_to_export['volume_level'].apply(
                lambda x: 0 if str(x).lower() == 'high_volume' else 1
            )
            sort_columns = ['volume_priority', 'balanced_reversion_count', 'reversion_consistency_score',
                            'cointegration_stability_score', 'half_life_days']
            sort_ascending = [True, False, False, False, True]
            print(f"   📊 Volume prioritization ENABLED: 'high_volume' first → balanced_reversion_count DESC "
                  f"→ reversion_consistency_score DESC")
        else:
            sort_columns = ['balanced_reversion_count', 'reversion_consistency_score',
                            'cointegration_stability_score', 'half_life_days']
            sort_ascending = [False, False, False, True]
            print("   📊 No volume_level column — ranking by balanced_reversion_count DESC → consistency DESC")

        df_to_export = df_to_export.sort_values(
            by=sort_columns,
            ascending=sort_ascending
        ).reset_index(drop=True)

        if 'volume_priority' in df_to_export.columns:
            df_to_export = df_to_export.drop(columns=['volume_priority'])

        print("   📋 Sorted by: volume_priority ASC → balanced_reversion_count DESC → "
              "reversion_consistency_score DESC → stability DESC → half_life ASC")

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
                  f"| consistency={best['reversion_consistency_score']:.3f} "
                  f"| mean_interval={best['mean_reversion_interval_days']:.1f}d "
                  f"| max_gap={best['max_reversion_gap_days']:.0f}d "
                  f"| stability={best.get('cointegration_stability_score', 'N/A'):.4f} "
                  f"| half_life={best['half_life_days']:.1f} days | volume={best.get('volume_level', 'N/A')}")

        return str(output_path)

    def summary(self) -> None:
        if self.df is None:
            return
        print("\n📊 Z-SCORE RANKING SUMMARY")
        print("=" * 70)
        cols = ['balanced_reversion_count', 'total_reversions', 'reversion_consistency_score',
                'mean_reversion_interval_days', 'max_reversion_gap_days',
                'signals_per_year', 'cointegration_stability_score', 'half_life_days']
        cols = [c for c in cols if c in self.df.columns]
        print(self.df[cols].describe().round(3))
        print(f"\nTotal pairs: {len(self.df):,}")
        if 'volume_level' in self.df.columns:
            high_vol = (self.df['volume_level'].str.lower() == 'high_volume').sum()
            print(f"   High volume pairs     : {high_vol:,}")
            print(f"   Other volume pairs    : {len(self.df) - high_vol:,}")


# =======================================================================
# MAIN EXECUTION
# =======================================================================
if __name__ == "__main__":
    processor = ZscoreDataProcessor(INPUT_CSV)
    
    print("\n" + "="*80)
    print("🔬 STEP 1: Computing z-score reversion metrics + temporal consistency...")
    processor.add_zscore_reversion_metrics()
    
    if PLOT_DISTRIBUTION:
        print("\n🎨 STEP 2: Generating reversion opportunities chart...")
        processor.plot_reversion_distribution()
    
    print("\n💾 STEP 3: Exporting final z-score-ranked CSV...")
    processor.export_filtered()
    
    processor.summary()
    print("="*80)
    print("✅ filter_by_zscore.py finished! Ready for trading.")
