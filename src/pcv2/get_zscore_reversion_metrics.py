#!/usr/bin/env python3
"""
Standalone Z-Score Reversion Metrics Calculator (March 2026)
===========================================================
Run for a single pair:
    python get_zscore_reversion_metrics.py ETH BTC

Or with options:
    python get_zscore_reversion_metrics.py ETH BTC --z-upper 1.5 --revert-confirm 0.1 --months 18 --csv

Now with its own local DEFAULT_CSV_FILE at the top (independent of config.py).
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from cointegration_engine import compute_cointegration
from config import DEFAULT_COINTEGRATION_METHOD   # only this is still imported

# ====================== CONFIG (change these!) ======================
# ←←← THIS IS THE NEW PART YOU ASKED FOR
DEFAULT_CSV_FILE: str = "top300_hourly_18months_combined.csv"      
Z_UPPER_THRESHOLD: float = 1.0
Z_LOWER_THRESHOLD: float = -1.0
REVERT_CONFIRM_LEVEL: float = 0.25
MAX_MONTHS_FOR_ZSCORE: int = 18
# =====================================================================


def compute_zscore_reversion_metrics(
    sym1: str,
    sym2: str,
    price_df: Optional[pd.DataFrame] = None,
    z_upper: float = Z_UPPER_THRESHOLD,
    z_lower: float = Z_LOWER_THRESHOLD,
    revert_confirm: float = REVERT_CONFIRM_LEVEL,
    max_months: int = MAX_MONTHS_FOR_ZSCORE,
    verbose: bool = True,          # ← False = silent when called from filter_by_zscore
) -> Dict:
    """
    Compute balanced z-score reversion metrics for ONE pair.
    Returns a dict with all columns that filter_by_zscore.py expects.
    """
    sym1, sym2 = sym1.upper(), sym2.upper()

    # Load price data once (if not pre-loaded by batch script)
    if price_df is None:
        if verbose:
            print(f"   📥 Loading price data from: {DEFAULT_CSV_FILE}")
            print(f"   📥 (last {max_months} months)...")
        price_df = pd.read_csv(DEFAULT_CSV_FILE, parse_dates=['datetime'])
        end_date = price_df['datetime'].max()
        days_back = int(max_months * 30.437 * 1.1)
        price_df = price_df[price_df['datetime'] >= (end_date - pd.Timedelta(days=days_back))].copy()
        if verbose:
            print(f"   → {len(price_df):,} hourly bars loaded")

    pair_data = price_df[price_df['symbol'].isin([sym1, sym2])].copy()
    if len(pair_data) < 500:
        if verbose:
            print(f"   ⚠️  Not enough data for {sym1}-{sym2} ({len(pair_data)} bars)")
        return _empty_metrics(sym1, sym2)

    pivot = pair_data.pivot(index='datetime', columns='symbol', values='close').dropna()
    if sym1 not in pivot.columns or sym2 not in pivot.columns or len(pivot) < 500:
        if verbose:
            print(f"   ⚠️  Missing data after pivot for {sym1}-{sym2}")
        return _empty_metrics(sym1, sym2)

    p1 = pivot[sym1]
    p2 = pivot[sym2]

    try:
        result = compute_cointegration(p1, p2, method=DEFAULT_COINTEGRATION_METHOD)

        # Robust hedge_ratio extraction (works for Johansen or any method)
        if hasattr(result, 'hedge_ratio'):
            hedge = float(result.hedge_ratio)
        elif hasattr(result, 'beta'):
            hedge = float(result.beta[0]) if isinstance(result.beta, (list, np.ndarray)) else float(result.beta)
        else:
            hedge = 1.0

        # Cointegrated spread (log prices)
        spread = np.log(p1) - hedge * np.log(p2)
        zscore = (spread - spread.mean()) / spread.std(ddof=0)

        # Count completed round-trips
        up = down = 0
        idx = 0
        n = len(zscore)
        while idx < n:
            z = zscore.iloc[idx]
            if z > z_upper:
                for j in range(idx + 1, n):
                    if zscore.iloc[j] < revert_confirm:
                        up += 1
                        idx = j
                        break
                else:
                    idx = n
            elif z < z_lower:
                for j in range(idx + 1, n):
                    if zscore.iloc[j] > -revert_confirm:
                        down += 1
                        idx = j
                        break
                else:
                    idx = n
            else:
                idx += 1

        total = up + down
        balanced = min(up, down)

        # Normalize to yearly frequency
        hours = (zscore.index[-1] - zscore.index[0]).total_seconds() / 3600
        data_years = hours / (24 * 365.25) if hours > 0 else np.nan
        signals_per_year = total / data_years if data_years > 0 else np.nan

        metrics = {
            'pair': f"{sym1}-{sym2}",
            'symbol1': sym1,
            'symbol2': sym2,
            'zscore_up_reversions': up,
            'zscore_down_reversions': down,
            'balanced_reversion_count': balanced,
            'total_reversions': total,
            'data_years': data_years,
            'signals_per_year': signals_per_year,
            'zscore_threshold_up': z_upper,
            'zscore_threshold_down': z_lower,
            'revert_confirm_level': revert_confirm,
        }

        if verbose:
            print(f"   ✅ {sym1}-{sym2} → balanced={balanced} | up={up} | down={down} | signals/yr={signals_per_year:.2f}")

        return metrics

    except Exception as e:
        if verbose:
            print(f"   ❌ Error computing {sym1}-{sym2}: {e}")
        return _empty_metrics(sym1, sym2)


def _empty_metrics(sym1: str, sym2: str) -> Dict:
    """Fallback when data or cointegration fails."""
    return {
        'pair': f"{sym1}-{sym2}",
        'symbol1': sym1,
        'symbol2': sym2,
        'zscore_up_reversions': 0,
        'zscore_down_reversions': 0,
        'balanced_reversion_count': 0,
        'total_reversions': 0,
        'data_years': np.nan,
        'signals_per_year': np.nan,
        'zscore_threshold_up': Z_UPPER_THRESHOLD,
        'zscore_threshold_down': Z_LOWER_THRESHOLD,
        'revert_confirm_level': REVERT_CONFIRM_LEVEL,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute z-score reversion metrics for a single pair")
    parser.add_argument("sym1", help="First symbol (e.g. ETH)")
    parser.add_argument("sym2", help="Second symbol (e.g. BTC)")
    parser.add_argument("--z-upper", type=float, default=Z_UPPER_THRESHOLD, help="Upper z-score trigger")
    parser.add_argument("--z-lower", type=float, default=Z_LOWER_THRESHOLD, help="Lower z-score trigger")
    parser.add_argument("--revert-confirm", type=float, default=REVERT_CONFIRM_LEVEL, help="Reversion confirmation level")
    parser.add_argument("--months", type=int, default=MAX_MONTHS_FOR_ZSCORE, help="Lookback months")
    parser.add_argument("--csv", action="store_true", help="Save one-line CSV row")
    args = parser.parse_args()

    metrics = compute_zscore_reversion_metrics(
        args.sym1, args.sym2,
        z_upper=args.z_upper,
        z_lower=args.z_lower,
        revert_confirm=args.revert_confirm,
        max_months=args.months,
        verbose=True,                  # always show output when running standalone
    )

    if args.csv:
        out_path = Path(f"zscore_metrics_{args.sym1}_{args.sym2}.csv")
        pd.DataFrame([metrics]).to_csv(out_path, index=False)
        print(f"   💾 One-line CSV saved → {out_path}")


if __name__ == "__main__":
    main()
