import pandas as pd
from pathlib import Path
from typing import Optional
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

# ====================== BLACKLIST CONFIG ======================
# Easy to extend later — just add more tickers here
BLACKLISTED_TOKENS: set[str] = {"DAI"}
# =====================================================================


class ZscoreDataProcessor:
    """
    Post-stability processor with volume prioritization,
    reversion frequency consistency, and manual blacklist support.
    Blacklisted pairs are kept but moved to the very bottom and clearly marked.
    """

    def __init__(self, csv_path: str):
        self.csv_path = Path(csv_path)
        self.df: Optional[pd.DataFrame] = None
        self._load_data()
        self.apply_blacklist()          # ← applied EARLY so we can skip calculations

    def _load_data(self) -> None:
        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")
        
        self.df = pd.read_csv(self.csv_path)
        print(f"✅ Loaded {len(self.df):,} pairs from '{self.csv_path.name}'")
        print(f"   Columns: {list(self.df.columns)}\n")

    def apply_blacklist(self) -> None:
        """Apply manual blacklist immediately — pairs kept but will skip heavy computation."""
        if self.df is None or len(self.df) == 0 or not BLACKLISTED_TOKENS:
            self.df['is_blacklisted'] = False
            self.df['blacklist_reason'] = pd.NA
            return

        print(f"\n🚫 Applying manual blacklist ({BLACKLISTED_TOKENS})")
        print("   Blacklisted pairs will skip z-score calculations and be pushed to bottom")

        self.df = self.df.copy()
        self.df['is_blacklisted'] = (
            self.df['symbol1'].isin(BLACKLISTED_TOKENS) |
            self.df['symbol2'].isin(BLACKLISTED_TOKENS)
        )
        self.df['blacklist_reason'] = np.where(
            self.df['is_blacklisted'], 'manual_blacklist', pd.NA
        )

        black_count = self.df['is_blacklisted'].sum()
        print(f"   → {black_count:,} pairs will be skipped for calculations and marked 'manual_blacklist'\n")

    def add_zscore_reversion_metrics(self) -> None:
        if self.df is None or len(self.df) == 0:
            print("❌ No data available.")
            return

        # Separate clean pairs from blacklisted
        clean_df = self.df[~self.df['is_blacklisted']].copy()
        black_df = self.df[self.df['is_blacklisted']].copy()

        print(f"\n🔬 COMPUTING Z-SCORE REVERSION METRICS (±{Z_UPPER_THRESHOLD} → revert past ±{REVERT_CONFIRM_LEVEL})")
        print("   Computing temporal frequency consistency of reversions")
        print(f"   Using last {MAX_MONTHS_FOR_ZSCORE} months of price data")
        print(f"   → Only on {len(clean_df):,} non-blacklisted pairs (blacklisted pairs skipped)")

        if len(clean_df) == 0:
            print("   ⚠️  All pairs are blacklisted — skipping all computations")
            self._zero_blacklisted_metrics()
            return

        # Load price data ONCE (shared by all clean pairs)
        price_df = pd.read_csv(DEFAULT_CSV_FILE, parse_dates=['datetime'])
        end_date = price_df['datetime'].max()
        days_back = int(MAX_MONTHS_FOR_ZSCORE * 30.437 * 1.1)
        price_df = price_df[price_df['datetime'] >= (end_date - pd.Timedelta(days=days_back))].copy()
        print(f"   → Loaded last {MAX_MONTHS_FOR_ZSCORE} months: {len(price_df):,} hourly bars\n")

        up_revs = []
        down_revs = []
        consistency_scores = []
        mean_intervals = []
        max_gaps = []

        for row in tqdm(clean_df.itertuples(index=False), total=len(clean_df),
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

            if len(timestamps) >= 2:
                ts_clean = pd.to_datetime(timestamps).tz_localize(None)
                deltas = (np.diff(ts_clean.values) / np.timedelta64(1, 'D')).astype(float)
                mean_delta = np.mean(deltas)
                std_delta = np.std(deltas)
                cv = std_delta / mean_delta if mean_delta > 0 else 0.0
                score = 1 / (1 + cv)
                max_gap = float(np.max(deltas))
            else:
                score = 0.0
                mean_delta = np.nan
                max_gap = np.nan

            consistency_scores.append(score)
            mean_intervals.append(mean_delta)
            max_gaps.append(max_gap)

        # Attach metrics to clean pairs
        clean_df['zscore_up_reversions'] = up_revs
        clean_df['zscore_down_reversions'] = down_revs
        clean_df['balanced_reversion_count'] = [min(u, d) for u, d in zip(up_revs, down_revs)]
        clean_df['total_reversions'] = [u + d for u, d in zip(up_revs, down_revs)]
        clean_df['reversion_consistency_score'] = consistency_scores
        clean_df['mean_reversion_interval_days'] = mean_intervals
        clean_df['max_reversion_gap_days'] = max_gaps

        if 'overlap_hours' in clean_df.columns:
            clean_df['data_years'] = clean_df['overlap_hours'] / (24 * 365.25)
            clean_df['signals_per_year'] = clean_df['total_reversions'] / clean_df['data_years'].replace(0, np.nan)

        # Zero-out blacklisted pairs
        self._zero_blacklisted_metrics(black_df)

        # Merge back
        self.df = pd.concat([clean_df, black_df], ignore_index=True)

        mean_balanced = clean_df['balanced_reversion_count'].mean()
        mean_consistency = clean_df['reversion_consistency_score'].mean()
        print(f"\n✅ Z-score metrics added! Mean balanced reversions (clean pairs): {mean_balanced:.2f}")
        print(f"   Mean consistency score (clean pairs): {mean_consistency:.3f}\n")

    def _zero_blacklisted_metrics(self, black_df: Optional[pd.DataFrame] = None) -> None:
        """Helper: set zero/NaN metrics on blacklisted pairs."""
        if black_df is None:
            black_df = self.df[self.df['is_blacklisted']]
        black_df['zscore_up_reversions'] = 0
        black_df['zscore_down_reversions'] = 0
        black_df['balanced_reversion_count'] = 0
        black_df['total_reversions'] = 0
        black_df['reversion_consistency_score'] = 0.0
        black_df['mean_reversion_interval_days'] = np.nan
        black_df['max_reversion_gap_days'] = np.nan
        if 'overlap_hours' in black_df.columns:
            black_df['signals_per_year'] = np.nan

    def export_filtered(self, output_path: Optional[str] = None) -> str:
        if self.df is None:
            raise ValueError("No data to export.")

        df_to_export = self.df.copy()

        # Sorting — blacklist is now the PRIMARY key
        df_to_export['blacklist_priority'] = df_to_export['is_blacklisted'].astype(int)

        if 'volume_level' in df_to_export.columns:
            df_to_export['volume_priority'] = df_to_export['volume_level'].apply(
                lambda x: 0 if str(x).lower() == 'high_volume' else 1
            )
            sort_columns = ['blacklist_priority', 'volume_priority', 'balanced_reversion_count',
                            'reversion_consistency_score', 'cointegration_stability_score', 'half_life_days']
            sort_ascending = [True, True, False, False, False, True]
        else:
            sort_columns = ['blacklist_priority', 'balanced_reversion_count', 'reversion_consistency_score',
                            'cointegration_stability_score', 'half_life_days']
            sort_ascending = [True, False, False, False, True]

        df_to_export = df_to_export.sort_values(
            by=sort_columns,
            ascending=sort_ascending
        ).reset_index(drop=True)

        # Drop temporary sort helpers
        temp_cols = ['blacklist_priority']
        if 'volume_priority' in df_to_export.columns:
            temp_cols.append('volume_priority')
        df_to_export = df_to_export.drop(columns=temp_cols, errors='ignore')

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
            status = " ← MANUAL BLACKLIST" if best['is_blacklisted'] else ""
            print(f"   🏆 Top pair: {best['pair']}{status} | balanced_reversions={best['balanced_reversion_count']} "
                  f"| consistency={best['reversion_consistency_score']:.3f} "
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
        blacklisted = self.df['is_blacklisted'].sum()
        print(f"   Blacklisted pairs     : {blacklisted:,}  ← skipped calculations, moved to bottom")
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
    print("🔬 STEP 1: Computing z-score reversion metrics + temporal consistency (skipping blacklisted)...")
    processor.add_zscore_reversion_metrics()
    
    print("\n💾 STEP 2: Exporting final z-score-ranked CSV...")
    processor.export_filtered()
    
    processor.summary()
    print("="*80)
    print("✅ filter_by_zscore.py finished! Ready for trading.")
    if BLACKLISTED_TOKENS:
        print(f"   Active blacklist: {BLACKLISTED_TOKENS}")
