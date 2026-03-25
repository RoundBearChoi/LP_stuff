import pandas as pd
import argparse
import warnings
from contextlib import redirect_stdout
import io
from tqdm import tqdm
from backtester import VolatilityHarvestingBacktester

warnings.filterwarnings('ignore')


class SilentVolatilityHarvestingBacktester(VolatilityHarvestingBacktester):
    """Subclass of the original backtester that disables plotting and most console output.
    
    This is essential for batch-processing thousands of pairs:
    - Prevents generation of 10,000+ PNG files (huge disk usage + slow matplotlib calls).
    - Suppresses purchasing-power prints and final results table (we capture metrics programmatically instead).
    - Keeps all the core calculation logic 100% identical to your original backtester.py.
    """
    def plot_results(self):
        """Completely skip plot generation and file I/O."""
        pass

    def _print_purchasing_power(self):
        """Quiet mode – we don't need the purchasing-power messages repeated 42k times."""
        pass

    def _print_results(self):
        """Quiet mode – metrics are extracted directly into the results DataFrame."""
        pass


def run_backtest_for_pair(symbol1: str, symbol2: str,
                          csv_path='top300_hourly_18months_combined.csv',
                          backtest_months=18,
                          target_weight_a=0.50,
                          fee_rate=0.01,
                          **kwargs):
    """Run a single volatility-harvesting backtest using your original class logic.
    
    Returns a dict of key performance numbers (or error info) that will be merged
    into the final ranked DataFrame.
    """
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

        # Full suppression of internal prints while still running every calculation
        with redirect_stdout(io.StringIO()):
            backtester.run_backtest()

        # Extract Strategy metrics (exactly the same columns your original script produces)
        metrics = backtester.metrics
        strategy = metrics.loc['Strategy']
        bh = metrics.loc['BuyHold_50/50']

        # Rebalance & trading stats (directly from the portfolio DataFrame)
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

    parser.add_argument('--input-csv', type=str,
                        default='filtered_by_volume_johansen_one_direction_18m_top42778.csv',
                        help='Path to the filtered pairs CSV (the one you provided)')
    parser.add_argument('--max-pairs', type=int, default=None,
                        help='Limit to first N pairs (highly recommended for testing – 42k pairs = many hours)')
    parser.add_argument('--target-weight-a', type=float, default=0.50,
                        help='Target weight for Asset A (same as backtester)')
    parser.add_argument('--fee-rate', type=float, default=0.01,
                        help='Trading fee rate')
    parser.add_argument('--csv-path', type=str,
                        default='top300_hourly_18months_combined.csv',
                        help='Path to the hourly combined price data')

    args = parser.parse_args()

    # ====================== LOAD PAIRS ======================
    print(f"📂 Loading pairs from: {args.input_csv}")
    df_pairs = pd.read_csv(args.input_csv)
    print(f"   Found {len(df_pairs):,} candidate pairs.\n")

    if args.max_pairs is not None and args.max_pairs > 0:
        df_pairs = df_pairs.head(args.max_pairs)
        print(f"🔬 Running only the first {args.max_pairs} pairs (testing mode).\n")

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

        # Merge original row + new backtest metrics
        result_row = row.to_dict().copy()
        result_row.update(metrics)
        results_list.append(result_row)

    # ====================== CREATE & RANK RESULTS ======================
    results_df = pd.DataFrame(results_list)

    # Rank from highest strategy return → lowest (exactly what you asked for)
    if 'strategy_total_return_pct' in results_df.columns:
        results_df = results_df.sort_values(
            by='strategy_total_return_pct',
            ascending=False
        ).reset_index(drop=True)
        # Add a clean rank column
        results_df.insert(0, 'rank', range(1, len(results_df) + 1))

    # ====================== OUTPUT FILENAME (matches your requested format) ======================
    # Example: filtered_by_volume_johansen_one_direction_18m_top42778.csv
    #   → filtered_by_backtester_johansen_one_direction_18m_top42778.csv
    output_csv = args.input_csv.replace('volume', 'backtester').replace('_sample', '')
    if not output_csv.endswith('.csv'):
        output_csv += '.csv'

    # ====================== SAVE & SUMMARY ======================
    results_df.to_csv(output_csv, index=False)

    print(f"\n✅ DONE! Ranked backtest results saved to:")
    print(f"   📄 {output_csv}")
    print(f"   Total pairs processed: {len(results_df):,}")
    print(f"   Successful backtests: {results_df['backtest_success'].sum():,}\n")

    # Show top 10 preview
    if 'rank' in results_df.columns:
        print("🏆 Top 10 pairs by Strategy Total Return (%):")
        top10_cols = ['rank', 'pair', 'strategy_total_return_pct', 'strategy_cagr_pct',
                      'outperformance_vs_bh_pct', 'rebalances', 'strategy_max_dd_pct']
        print(results_df.head(10)[top10_cols].round(2).to_string(index=False))

    print("\n💡 Tip: Re-run with --max-pairs 500 (or remove the flag for the full list) once you're happy with the setup.")
    print("   The output CSV contains EVERY original column from your filtered file + all the new backtest metrics.")
