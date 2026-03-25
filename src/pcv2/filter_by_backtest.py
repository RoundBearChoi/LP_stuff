import pandas as pd
import argparse
import warnings
from contextlib import redirect_stdout
import io
from tqdm import tqdm
from backtester import VolatilityHarvestingBacktester
import os
import matplotlib.pyplot as plt

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
                          backtest_months=3,
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


def plot_rebalance_distribution(results_df: pd.DataFrame, output_csv: str):
    """Draw rebalances ordered highest → lowest + 20th/80th percentile lines + extra bottom text."""
    if 'rebalances' not in results_df.columns or results_df.empty:
        print("⚠️  No 'rebalances' column found or DataFrame is empty – skipping chart.")
        return

    # Work on a copy
    plot_df = results_df.copy()
    if 'rank' in plot_df.columns:
        plot_df = plot_df.drop(columns=['rank'])

    plot_df = plot_df.sort_values(by='rebalances', ascending=False).reset_index(drop=True)
    plot_df.insert(0, 'rank', range(1, len(plot_df) + 1))

    p20 = plot_df['rebalances'].quantile(0.20)
    p80 = plot_df['rebalances'].quantile(0.80)

    # Print statistics (same as before)
    print(f"\n📊 Rebalance Statistics (N = {len(plot_df):,})")
    print(f"   Min      : {plot_df['rebalances'].min():,.0f}")
    print(f"   Median   : {plot_df['rebalances'].median():,.0f}")
    print(f"   Mean     : {plot_df['rebalances'].mean():,.1f}")
    print(f"   20th %ile: {p20:,.0f}")
    print(f"   80th %ile: {p80:,.0f}")
    print(f"   Max      : {plot_df['rebalances'].max():,.0f}")

    # === CHART WITH EXTRA BOTTOM SPACE ===
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.plot(plot_df['rank'], plot_df['rebalances'],
            marker='.', linestyle='-', color='tab:blue', alpha=0.7, label='Rebalances per pair')
    
    ax.axhline(p20, color='tab:green', linestyle='--', linewidth=2.5,
               label=f'20th Percentile ({p20:,.0f})')
    ax.axhline(p80, color='tab:red', linestyle='--', linewidth=2.5,
               label=f'80th Percentile ({p80:,.0f})')

    ax.set_xlabel('Rank (1 = Highest Rebalances)')
    ax.set_ylabel('Number of Rebalances')
    ax.set_title('Rebalance Count Distribution Across All Pairs\n'
                 '(Sorted Highest to Lowest)')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    plt.subplots_adjust(bottom=0.22)

    fig.text(0.05, 0.08, f"20th Percentile rebalance count: {p20:,.0f}",
             fontsize=11, color='tab:green', fontweight='bold')
    fig.text(0.05, 0.04, f"80th Percentile rebalance count: {p80:,.0f}",
             fontsize=11, color='tab:red', fontweight='bold')

    chart_path = output_csv.replace('.csv', '_rebalances_chart.png')
    plt.savefig(chart_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"📈 Updated rebalance chart saved as: {chart_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='filtered_by_backtest.py – runs volatility harvesting on every pair '
                    'from your Johansen-filtered CSV and ranks them by highest rebalance count.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--top-volume-percent', type=float, default=30.0,
                        help='Default: run only the top X%% highest-volume pairs '
                             '(sorted by volume_percentile descending). '
                             'Set to 0 or 100 to run the full list.')

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

    if args.max_pairs is not None and args.max_pairs > 0:
        df_pairs = df_pairs.head(args.max_pairs)
        print(f"🔬 Running only the first {args.max_pairs} pairs (manual --max-pairs override).\n")
    else:
        if 0 < args.top_volume_percent < 100:
            df_pairs = df_pairs.sort_values(by='volume_percentile', ascending=False).reset_index(drop=True)
            n_pairs = int(len(df_pairs) * (args.top_volume_percent / 100))
            df_pairs = df_pairs.head(n_pairs)
            print(f"📊 Default mode: running top {args.top_volume_percent}% by volume → {n_pairs:,} pairs.\n")
        else:
            print(f"📊 Running full dataset ({len(df_pairs):,} pairs) because --top-volume-percent={args.top_volume_percent}.\n")

    # ====================== OUTPUT FILENAME ======================
    output_csv = args.input_csv.replace('volume', 'backtester').replace('_sample', '')
    if not output_csv.endswith('.csv'):
        output_csv += '.csv'

    # ====================== CHECK IF OUTPUT FILE ALREADY EXISTS ======================
    plot_only = False
    if os.path.exists(output_csv):
        response = input(f"\n📄 Output file '{output_csv}' already exists.\n"
                         f"Do you want to skip backtesting and only generate the chart? (y/n): ").strip().lower()
        if response in ['y', 'yes']:
            plot_only = True
            print("🔄 Loading existing results and generating chart only...")
            results_df = pd.read_csv(output_csv)
            print(f"   Loaded {len(results_df):,} pairs from previous run.")
        else:
            print("🚀 Proceeding with full backtests (existing file will be overwritten)...\n")
    else:
        print(f"📂 No existing output file found. Will create: {output_csv}\n")

    # ====================== RUN BACKTESTS OR LOAD EXISTING ======================
    if not plot_only:
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

        results_df = pd.DataFrame(results_list)

        if 'rebalances' in results_df.columns and not results_df.empty:
            # ====================== NEW ORDERING LOGIC (per your request) ======================
            p20 = results_df['rebalances'].quantile(0.20)
            p80 = results_df['rebalances'].quantile(0.80)

            print(f"\n📊 Rebalance Percentiles for CSV ordering:")
            print(f"   20th percentile : {p20:,.0f}")
            print(f"   80th percentile : {p80:,.0f}")

            results_df['is_middle'] = (
                (results_df['rebalances'] >= p20) &
                (results_df['rebalances'] <= p80)
            )

            results_df = results_df.sort_values(
                by=['is_middle', 'rebalances'],
                ascending=[False, False]
            ).reset_index(drop=True)

            results_df.insert(0, 'rank', range(1, len(results_df) + 1))

            middle_count = results_df['is_middle'].sum()
            print(f"   → Middle group (20–80th %ile) : {middle_count:,} pairs (now at top)")
            print(f"   → Outliers (outside range)    : {len(results_df)-middle_count:,} pairs (moved to bottom)")

            results_df = results_df.drop(columns=['is_middle'])

        results_df.to_csv(output_csv, index=False)
        print(f"\n✅ Backtest results saved to: {output_csv}")
        print(f"   Total pairs processed: {len(results_df):,}")
        print(f"   Successful backtests: {results_df['backtest_success'].sum():,}\n")

    # ====================== GENERATE CHART ======================
    if 'results_df' in locals() and not results_df.empty:
        plot_rebalance_distribution(results_df, output_csv)
    else:
        print("⚠️  No results available to plot.")

    # Top 10 preview
    if 'results_df' in locals() and 'rank' in results_df.columns:
        print("\n🏆 Top 10 pairs by Rebalance Count (highest → lowest):")
        top10_cols = ['rank', 'pair', 'rebalances', 'strategy_total_return_pct', 'strategy_cagr_pct',
                      'outperformance_vs_bh_pct', 'strategy_max_dd_pct']
        print(results_df.head(10)[top10_cols].round(2).to_string(index=False))

    print("\n💡 Tips:")
    print("   • Run with --top-volume-percent 0 to process everything")
    print("   • Use --max-pairs 50 for quick testing")
    print("   • The chart is always generated at the end")
