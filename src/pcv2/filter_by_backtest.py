import pandas as pd
import argparse
import warnings
from contextlib import redirect_stdout
import io
from tqdm import tqdm
from backtester import VolatilityHarvestingBacktester

warnings.filterwarnings('ignore')


class SilentVolatilityHarvestingBacktester(VolatilityHarvestingBacktester):
    """Silent subclass – no plots, no console spam for batch runs."""
    def plot_results(self):
        pass

    def _print_purchasing_power(self):
        pass

    def _print_results(self):
        pass


def run_backtest_for_pair(symbol1: str, symbol2: str,
                          csv_path='top300_hourly_18months_combined.csv',
                          backtest_months=18,
                          target_weight_a=0.50,
                          fee_rate=0.01,
                          **kwargs):
    """Run one volatility-harvesting backtest (identical logic to your original backtester)."""
    try:
        backtester = SilentVolatilityHarvestingBacktester(
            csv_path=csv_path,
            asset_a=symbol1.upper(),
            asset_b=symbol2.upper(),
            target_weight_a=target_weight_a,
            fee_rate=fee_rate,
            backtest_months=backtest_months,
            **kwargs
        )

        with redirect_stdout(io.StringIO()):
            backtester.run_backtest()

        metrics = backtester.metrics
        strategy = metrics.loc['Strategy']
        bh = metrics.loc['BuyHold_50/50']

        rebalances = int(backtester.portfolio['rebalance'].sum())
        total_trade_volume_usd = float(backtester.portfolio['trade'].sum())

        return {
            'strategy_final_value': float(strategy['Final Value (USD)']),
            'strategy_total_return_pct': float(strategy['Total Return (%)']),
            'strategy_cagr_pct': float(strategy['CAGR (%)']),
            'strategy_max_dd_pct': float(strategy['Max DD (%)']),
            'strategy_vol_ann_pct': float(strategy['Vol (ann.)']),
            'strategy_sharpe': float(strategy['Sharpe (rf=0)']),
            'bh_total_return_pct': float(bh['Total Return (%)']),
            'outperformance_vs_bh_pct': float(strategy['Total Return (%)'] - bh['Total Return (%)']),
            'a_only_total_return_pct': float(metrics.loc[f'{backtester.asset_a}_100%', 'Total Return (%)']),
            'b_only_total_return_pct': float(metrics.loc[f'{backtester.asset_b}_100%', 'Total Return (%)']),
            'rebalances': rebalances,
            'total_trade_volume_usd': total_trade_volume_usd,
            'backtest_success': True,
            'error': None
        }

    except Exception as e:
        return {
            'backtest_success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='filtered_by_backtest.py – runs volatility harvesting on every pair '
                    'from your Johansen-filtered CSV and ranks them by highest return.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # === NEW DEFAULT BEHAVIOR ===
    parser.add_argument('--top-volume-percent', type=float, default=30.0,
                        help='Default: run only the top X%% highest-volume pairs '
                             '(sorted by volume_percentile descending). '
                             'Set to 0 or 100 to run the full list.')

    # === Existing flags (kept exactly as before) ===
    parser.add_argument('--max-pairs', type=int, default=None,
                        help='Manual limit (for testing). Overrides --top-volume-percent when set.')
    parser.add_argument('--target-weight-a', type=float, default=0.50,
                        help='Target weight for Asset A')
    parser.add_argument('--fee-rate', type=float, default=0.01,
                        help='Trading fee rate')
    parser.add_argument('--csv-path', type=str,
                        default='top300_hourly_18months_combined.csv',
                        help='Path to the hourly combined price data')
    parser.add_argument('--input-csv', type=str,
                        default='filtered_by_volume_johansen_one_direction_18m_top42778.csv',
                        help='Path to the filtered pairs CSV')

    args = parser.parse_args()

    # ====================== LOAD & FILTER PAIRS ======================
    print(f"📂 Loading pairs from: {args.input_csv}")
    df_pairs = pd.read_csv(args.input_csv)
    print(f"   Found {len(df_pairs):,} candidate pairs.")

    # === NEW: Auto-select top X% by volume (unless --max-pairs is used) ===
    if args.max_pairs is not None and args.max_pairs > 0:
        df_pairs = df_pairs.head(args.max_pairs)
        print(f"🔬 Running only the first {args.max_pairs} pairs (manual --max-pairs override).\n")
    else:
        if 0 < args.top_volume_percent < 100:
            # Sort by volume (robust – works even if CSV is not pre-sorted)
            df_pairs = df_pairs.sort_values(by='volume_percentile', ascending=False).reset_index(drop=True)
            n_pairs = int(len(df_pairs) * (args.top_volume_percent / 100))
            df_pairs = df_pairs.head(n_pairs)
            print(f"📊 Default mode: running top {args.top_volume_percent}% by volume → {n_pairs:,} pairs.\n")
        else:
            print(f"📊 Running full dataset ({len(df_pairs):,} pairs) because --top-volume-percent={args.top_volume_percent}.\n")

    # ====================== BATCH BACKTEST ======================
    results_list = []

    print("🚀 Starting batch volatility-harvesting backtests...\n")
    for idx, row in tqdm(df_pairs.iterrows(), total=len(df_pairs), desc="Backtesting pairs"):
        pair = row['pair']
        symbol1 = row['symbol1']
        symbol2 = row['symbol2']

        metrics = run_backtest_for_pair(
            symbol1=symbol1,
            symbol2=symbol2,
            csv_path=args.csv_path,
            target_weight_a=args.target_weight_a,
            fee_rate=args.fee_rate
        )

        result_row = row.to_dict().copy()
        result_row.update(metrics)
        results_list.append(result_row)

    # ====================== CREATE & RANK RESULTS ======================
    results_df = pd.DataFrame(results_list)

    if 'strategy_total_return_pct' in results_df.columns:
        results_df = results_df.sort_values(
            by='strategy_total_return_pct',
            ascending=False
        ).reset_index(drop=True)
        results_df.insert(0, 'rank', range(1, len(results_df) + 1))

    # ====================== OUTPUT FILENAME ======================
    output_csv = args.input_csv.replace('volume', 'backtester').replace('_sample', '')
    if not output_csv.endswith('.csv'):
        output_csv += '.csv'

    # ====================== SAVE & SUMMARY ======================
    results_df.to_csv(output_csv, index=False)

    print(f"\n✅ DONE! Ranked backtest results saved to:")
    print(f"   📄 {output_csv}")
    print(f"   Total pairs processed: {len(results_df):,}")
    print(f"   Successful backtests: {results_df['backtest_success'].sum():,}\n")

    # Top 10 preview
    if 'rank' in results_df.columns:
        print("🏆 Top 10 pairs by Strategy Total Return (%):")
        top10_cols = ['rank', 'pair', 'strategy_total_return_pct', 'strategy_cagr_pct',
                      'outperformance_vs_bh_pct', 'rebalances', 'strategy_max_dd_pct']
        print(results_df.head(10)[top10_cols].round(2).to_string(index=False))

    print("\n💡 Usage tips:")
    print("   • Default (no flags)          → top 30% by volume")
    print("   • python ... --top-volume-percent 50   → top 50%")
    print("   • python ... --max-pairs 100          → only first 100 (testing)")
    print("   • python ... --top-volume-percent 0    → full list")
    print("   The output CSV keeps ALL original columns + new backtest metrics.")
