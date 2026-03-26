#!/usr/bin/env python3
"""
Standalone Z-Score Reversion Visualizer (March 2026) — UPDATED
===============================================================
Run for a single pair (NOW NON-INTERACTIVE BY DEFAULT):
    python draw_zscore_reversion_metrics_charts.py ETH BTC

Or with options:
    python draw_zscore_reversion_metrics_charts.py ETH BTC \
        --z-upper 1.5 --revert-confirm 0.1 --months 18 \
        --dpi 300 --show

This version:
  • DEFAULT: no interactive window (just saves PNG silently — no pause)
  • DEFAULT DPI lowered to 150 (faster save, still crisp)
  • Added optional --show flag if you ever want the plot to pop up
  • 100% same numbers & logic as before
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# ====================== IMPORT SHARED LOGIC ======================
# We reuse the exact same computation function so the numbers are 100% identical
from get_zscore_reversion_metrics import (
    compute_zscore_reversion_metrics,
    DEFAULT_CSV_FILE,
    Z_UPPER_THRESHOLD,
    Z_LOWER_THRESHOLD,
    REVERT_CONFIRM_LEVEL,
    MAX_MONTHS_FOR_ZSCORE,
)

# ====================== PLOTTING CONFIG ======================
DEFAULT_FIGSIZE = (16, 10)
DEFAULT_DPI = 150          # ← CHANGED TO 150 as requested
DEFAULT_SAVE_PATH = "zscore_reversion_plot_{sym1}_{sym2}.png"


def _collect_reversion_events(
    zscore: pd.Series,
    z_upper: float,
    z_lower: float,
    revert_confirm: float,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Same exact loop as compute_zscore_reversion_metrics, but also records
    entry/exit timestamps and z-values for plotting.
    """
    up_events: List[Dict] = []
    down_events: List[Dict] = []
    idx = 0
    n = len(zscore)

    while idx < n:
        z = zscore.iloc[idx]
        ts = zscore.index[idx]

        if z > z_upper:
            entry = {"entry_ts": ts, "entry_z": float(z)}
            for j in range(idx + 1, n):
                if zscore.iloc[j] < revert_confirm:
                    exit_ts = zscore.index[j]
                    exit_z = float(zscore.iloc[j])
                    up_events.append({
                        **entry,
                        "exit_ts": exit_ts,
                        "exit_z": exit_z,
                        "duration_hours": (exit_ts - ts).total_seconds() / 3600,
                    })
                    idx = j
                    break
            else:
                idx = n
        elif z < z_lower:
            entry = {"entry_ts": ts, "entry_z": float(z)}
            for j in range(idx + 1, n):
                if zscore.iloc[j] > -revert_confirm:
                    exit_ts = zscore.index[j]
                    exit_z = float(zscore.iloc[j])
                    down_events.append({
                        **entry,
                        "exit_ts": exit_ts,
                        "exit_z": exit_z,
                        "duration_hours": (exit_ts - ts).total_seconds() / 3600,
                    })
                    idx = j
                    break
            else:
                idx = n
        else:
            idx += 1

    return up_events, down_events


def draw_zscore_reversion_chart(
    sym1: str,
    sym2: str,
    price_df: Optional[pd.DataFrame] = None,
    z_upper: float = Z_UPPER_THRESHOLD,
    z_lower: float = Z_LOWER_THRESHOLD,
    revert_confirm: float = REVERT_CONFIRM_LEVEL,
    max_months: int = MAX_MONTHS_FOR_ZSCORE,
    figsize: Tuple[int, int] = DEFAULT_FIGSIZE,
    dpi: int = DEFAULT_DPI,
    save_path: Optional[str] = None,
    show: bool = False,          # ← CHANGED DEFAULT TO False (no pause)
) -> None:
    """
    Full visualization pipeline. Reuses the official metrics function
    and adds rich Matplotlib charting.
    """
    sym1, sym2 = sym1.upper(), sym2.upper()

    # ── 1. Compute metrics (same numbers as get_zscore_reversion_metrics.py) ──
    metrics = compute_zscore_reversion_metrics(
        sym1, sym2, price_df,
        z_upper=z_upper,
        z_lower=z_lower,
        revert_confirm=revert_confirm,
        max_months=max_months,
        verbose=False,
    )

    # ── 2. Reload data + recompute spread & z-score for plotting ──
    if price_df is None:
        price_df = pd.read_csv(DEFAULT_CSV_FILE, parse_dates=['datetime'])
        end_date = price_df['datetime'].max()
        days_back = int(max_months * 30.437 * 1.1)
        price_df = price_df[price_df['datetime'] >= (end_date - pd.Timedelta(days=days_back))].copy()

    pair_data = price_df[price_df['symbol'].isin([sym1, sym2])].copy()
    pivot = pair_data.pivot(index='datetime', columns='symbol', values='close').dropna()

    if len(pivot) < 500 or sym1 not in pivot.columns or sym2 not in pivot.columns:
        print(f"   ⚠️  Not enough data for {sym1}-{sym2}")
        return

    p1 = pivot[sym1]
    p2 = pivot[sym2]

    # Same cointegration logic as the metrics script
    from cointegration_engine import compute_cointegration
    from config import DEFAULT_COINTEGRATION_METHOD
    result = compute_cointegration(p1, p2, method=DEFAULT_COINTEGRATION_METHOD)

    if hasattr(result, 'hedge_ratio'):
        hedge = float(result.hedge_ratio)
    elif hasattr(result, 'beta'):
        hedge = float(result.beta[0]) if isinstance(result.beta, (list, np.ndarray)) else float(result.beta)
    else:
        hedge = 1.0

    spread = np.log(p1) - hedge * np.log(p2)
    zscore = (spread - spread.mean()) / spread.std(ddof=0)

    # ── 3. Collect exact reversion events for markers/shading ──
    up_events, down_events = _collect_reversion_events(zscore, z_upper, z_lower, revert_confirm)

    # ── 4. Build the figure ──
    fig, axs = plt.subplots(3, 1, figsize=figsize, sharex=True,
                            gridspec_kw={'height_ratios': [3, 2, 4]})
    fig.suptitle(
        f"Z-Score Reversion Analysis — {sym1}-{sym2}\n"
        f"Balanced round-trips = {metrics['balanced_reversion_count']} | "
        f"Signals/year = {metrics['signals_per_year']:.2f} | "
        f"Data = {metrics['data_years']:.1f} years",
        fontsize=16, fontweight='bold', y=0.98
    )

    # Panel 1: Prices (twin axes)
    ax1 = axs[0]
    ax1_twin = ax1.twinx()
    ax1.plot(p1.index, p1, label=sym1, color='#1f77b4', linewidth=1.8)
    ax1_twin.plot(p2.index, p2, label=sym2, color='#ff7f0e', linewidth=1.8)
    ax1.set_ylabel(f"{sym1} Price (USD)", color='#1f77b4')
    ax1_twin.set_ylabel(f"{sym2} Price (USD)", color='#ff7f0e')
    ax1.tick_params(axis='y', labelcolor='#1f77b4')
    ax1_twin.tick_params(axis='y', labelcolor='#ff7f0e')
    ax1.legend(loc='upper left')
    ax1_twin.legend(loc='upper right')

    # Panel 2: Spread
    ax2 = axs[1]
    ax2.plot(spread.index, spread, color='purple', linewidth=1.5, alpha=0.9)
    ax2.set_ylabel("Log Spread", color='purple')
    ax2.axhline(0, color='gray', linestyle='--', alpha=0.5)

    # Panel 3: Z-Score (the star of the show)
    ax3 = axs[2]
    ax3.plot(zscore.index, zscore, color='black', linewidth=1.2, label='Z-Score')
    ax3.axhline(z_upper, color='red', linestyle='--', label=f'Upper trigger ({z_upper})')
    ax3.axhline(z_lower, color='green', linestyle='--', label=f'Lower trigger ({z_lower})')
    ax3.axhline(revert_confirm, color='red', linestyle=':', alpha=0.7, label=f'Revert confirm (+{revert_confirm})')
    ax3.axhline(-revert_confirm, color='green', linestyle=':', alpha=0.7, label=f'Revert confirm (-{revert_confirm})')
    ax3.axhline(0, color='gray', linestyle='-', alpha=0.4)

    # Shade completed trades
    for event in up_events:
        ax3.axvspan(event['entry_ts'], event['exit_ts'], color='red', alpha=0.12)
    for event in down_events:
        ax3.axvspan(event['entry_ts'], event['exit_ts'], color='green', alpha=0.12)

    # Entry / Exit markers
    for event in up_events:
        ax3.plot(event['entry_ts'], event['entry_z'], marker='^', color='red', markersize=9, label='_nolegend_')
        ax3.plot(event['exit_ts'], event['exit_z'], marker='o', color='darkred', markersize=7, label='_nolegend_')
    for event in down_events:
        ax3.plot(event['entry_ts'], event['entry_z'], marker='v', color='green', markersize=9, label='_nolegend_')
        ax3.plot(event['exit_ts'], event['exit_z'], marker='o', color='darkgreen', markersize=7, label='_nolegend_')

    ax3.set_ylabel("Z-Score")
    ax3.legend(loc='upper right', ncol=2, fontsize=9)
    ax3.grid(True, alpha=0.3)

    # Format x-axis
    for ax in axs:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        ax.tick_params(axis='x', rotation=45)

    plt.tight_layout(rect=[0, 0, 1, 0.95])

    # ── 5. Save & (optionally) Show ──
    if save_path is None:
        save_path = DEFAULT_SAVE_PATH.format(sym1=sym1, sym2=sym2)

    out_path = Path(save_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=dpi, bbox_inches='tight')
    print(f"   📊 Chart saved → {out_path.resolve()}")

    if show:
        plt.show()
    else:
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Draw beautiful z-score reversion charts (identical numbers to the metrics script)"
    )
    parser.add_argument("sym1", help="First symbol (e.g. ETH)")
    parser.add_argument("sym2", help="Second symbol (e.g. BTC)")
    parser.add_argument("--z-upper", type=float, default=Z_UPPER_THRESHOLD,
                        help="Upper z-score trigger (default: 1.0)")
    parser.add_argument("--z-lower", type=float, default=Z_LOWER_THRESHOLD,
                        help="Lower z-score trigger (default: -1.0)")
    parser.add_argument("--revert-confirm", type=float, default=REVERT_CONFIRM_LEVEL,
                        help="Reversion confirmation level (default: 0.25)")
    parser.add_argument("--months", type=int, default=MAX_MONTHS_FOR_ZSCORE,
                        help="Lookback months (default: 18)")
    parser.add_argument("--figsize", nargs=2, type=int, default=DEFAULT_FIGSIZE,
                        help="Figure size in inches (width height), default 16 10")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI,   # ← NOW DEFAULTS TO 150
                        help="DPI for saved PNG (default: 150)")
    parser.add_argument("--show", action="store_true",
                        help="Show interactive plot window (default: OFF — silent save only)")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output PNG path")
    args = parser.parse_args()

    draw_zscore_reversion_chart(
        sym1=args.sym1,
        sym2=args.sym2,
        z_upper=args.z_upper,
        z_lower=args.z_lower,
        revert_confirm=args.revert_confirm,
        max_months=args.months,
        figsize=tuple(args.figsize),
        dpi=args.dpi,
        save_path=args.output,
        show=args.show,          # now controlled by --show flag
    )

    # Also print the exact same metrics table for quick reference
    metrics = compute_zscore_reversion_metrics(
        args.sym1, args.sym2,
        z_upper=args.z_upper,
        z_lower=args.z_lower,
        revert_confirm=args.revert_confirm,
        max_months=args.months,
        verbose=False,
    )
    print("\n" + "="*80)
    print("METRICS SUMMARY (identical to get_zscore_reversion_metrics.py)")
    print("="*80)
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:25} : {v:10.4f}")
        else:
            print(f"  {k:25} : {v}")


if __name__ == "__main__":
    main()
