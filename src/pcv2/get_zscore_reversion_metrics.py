#!/usr/bin/env python3
"""
Standalone Z-Score Reversion Metrics Calculator (March 2026)
===========================================================
Run for a single pair:
    python get_zscore_reversion_metrics.py ETH BTC

Or with options:
    python get_zscore_reversion_metrics.py ETH BTC --z-upper 1.5 --revert-confirm 0.1 --months 18 --csv

NOW INCLUDES spread_std, spread_mean, and is_log_spread for safe % price-range conversion.
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Optional
from cointegration_engine import compute_cointegration
from config import DEFAULT_COINTEGRATION_METHOD

# ====================== CONFIG (change these!) ======================
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
    verbose: bool = True,
) -> Dict:
    """
    Compute balanced z-score reversion metrics for ONE pair.
    Returns spread statistics for safe % price-range conversion.
    """
    sym1, sym2 = sym1.upper(), sym2.upper()

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

        if hasattr(result, 'hedge_ratio'):
            hedge = float(result.hedge_ratio)
        elif hasattr(result, 'beta'):
            hedge = float(result.beta[0]) if isinstance(result.beta, (list, np.ndarray)) else float(result.beta)
        else:
            hedge = 1.0

        # Log-spread (standard for crypto)
        spread = np.log(p1) - hedge * np.log(p2)
        zscore = (spread - spread.mean()) / spread.std(ddof=0)

        # Spread stats for % conversion
        spread_std = float(spread.std(ddof=0))
        spread_mean = float(spread.mean())
        is_log_spread = True

        # Reversion timestamps
        up_reversion_times = []
        down_reversion_times = []

        up = down = 0
        idx = 0
        n = len(zscore)
        while idx < n:
            z = zscore.iloc[idx]
            if z > z_upper:
                for j in range(idx + 1, n):
                    if zscore.iloc[j] < revert_confirm:
                        up += 1
                        up_reversion_times.append(zscore.index[j])
                        idx = j
                        break
                else:
                    idx = n
            elif z < z_lower:
                for j in range(idx + 1, n):
                    if zscore.iloc[j] > -revert_confirm:
                        down += 1
                        down_reversion_times.append(zscore.index[j])
                        idx = j
                        break
                else:
                    idx = n
            else:
                idx += 1

        total = up + down
        balanced = min(up, down)

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
            'reversion_timestamps': sorted(up_reversion_times + down_reversion_times),
            'spread_std': spread_std,
            'spread_mean': spread_mean,
            'is_log_spread': is_log_spread,
        }

        if verbose:
            # Safe % print (no overflow)
            pct_approx = abs((np.exp(min(1.5 * spread_std, 20.0)) - 1) * 100) if spread_std > 0 else float('nan')
            print(f"   ✅ {sym1}-{sym2} → balanced={balanced} | up={up} | down={down} | signals/yr={signals_per_year:.2f} "
                  f"| spread_std={spread_std:.5f} | % range at Z±1.5 ≈ ±{pct_approx:.2f}%")

        return metrics

    except Exception as e:
        if verbose:
            print(f"   ❌ Error computing {sym1}-{sym2}: {e}")
        return _empty_metrics(sym1, sym2)


def _empty_metrics(sym1: str, sym2: str) -> Dict:
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
        'reversion_timestamps': [],
        'spread_std': 0.0,
        'spread_mean': 0.0,
        'is_log_spread': True,
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
        verbose=True,
    )

    if args.csv:
        out_path = Path(f"zscore_metrics_{args.sym1}_{args.sym2}.csv")
        pd.DataFrame([metrics]).to_csv(out_path, index=False)
        print(f"   💾 One-line CSV saved → {out_path}")


if __name__ == "__main__":
    main()
