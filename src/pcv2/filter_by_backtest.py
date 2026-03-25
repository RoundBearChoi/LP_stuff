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


# =============================================================================
# ==========================  EASY CONFIG SECTION  ============================
# =============================================================================
# Edit these defaults here — no need to type flags every time!
TOP_N_PAIRS = 10                   # e.g. 10, 15, 50, 100, 0 (0 = run all)
BACKTEST_MONTHS = 3                # ← NEW: number of recent months (latest → past X months)
MAX_PAIRS_OVERRIDE = None          # Set to e.g. 50 for quick testing (None = no limit)
TARGET_WEIGHT_A = 0.50
FEE_RATE = 0.01
CSV_PATH = 'top300_hourly_18months_combined.csv'
INPUT_CSV = 'filtered_by_volume_johansen_one_direction_18m_top42778.csv'
# =============================================================================


class SilentVolatilityHarvestingBacktester(VolatilityHarvestingBacktester):
    """Silent subclass – no plots, no console spam for batch runs."""
    def plot_results(self):
        pass

    def _print_purchasing_power(self):
        pass

    def _print_results(self):
        pass


def run_backtest_for_pair(symbol1: str, symbol2: str,
                          csv_path=CSV_PATH,
                          backtest_months=BACKTEST_MONTHS,
                          target_weight_a=TARGET_WEIGHT_A,
                          fee_rate=FEE_RATE,
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

    plot_df = results_df.copy()
    if 'rank' in plot_df.columns:
        plot_df = plot_df.drop(columns=['rank'])

    plot_df = plot_df.sort_values(by='rebalances', ascending=False).reset_index(drop=True)
    plot_df.insert(0, 'rank', range(1, len(plot_df) + 1))

    p20 = plot_df['rebalances'].quantile(0.20)
    p80 = plot_df['rebalances'].quantile(0.80)

    print(f"\n📊 Rebalance Statistics (N = {len(plot_df):,})")
    print(f"   Min      : {plot_df['rebalances'].min():,.0f}")
    print(f"   Median   : {plot_df['rebalances'].median():,.0f}")
    print(f"   Mean     : {plot_df['rebalances'].mean():,.1f}")
    print(f"   20th %ile: {p20:,.0f}")
    print(f"   80th %ile: {p80:,.0f}")
    print(f"   Max      : {plot_df['rebalances'].max():,.0f}")

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
        description='filtered_by_backtest.py – runs volatility harvesting on the top N '
                    'highest-volume pairs from your Johansen-filtered CSV and ranks them by highest rebalance count.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--top-n', type=int, default=TOP_N_PAIRS,
                        help='Run only the top N highest-volume pairs '
                             '(sorted by volume_percentile descending). '
                             'Set to 0 to run the full list.')
    parser.add_argument('--backtest-months', type=int, default=BACKTEST_MONTHS,
                        help='Number of recent months to run the backtest on '
                             '(from the latest date backwards).')
    parser.add_argument('--max-pairs', type=int, default=MAX_PAIRS_OVERRIDE,
                        help='Manual limit (for testing). Overrides --top-n when set.')
    parser.add_argument('--target-weight-a', type=float, default=TARGET_WEIGHT_A,
                        help='Target weight for Asset A')
    parser.add_argument('--fee-rate', type=float, default=FEE_RATE,
                        help='Trading fee rate')
    parser.add_argument('--csv-path', type=str, default=CSV_PATH,
                        help='Path to the hourly combined price data')
    parser.add_argument('--input-csv', type=str, default=INPUT_CSV,
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
        if args.top_n is not None and args.top_n > 0:
            df_pairs = df_pairs.sort_values(by='volume_percentile', ascending=False).reset_index(drop=True)
            n_pairs = min(args.top_n, len(df_pairs))
            df_pairs = df_pairs.head(n_pairs)
            print(f"📊 Running top {n_pairs:,} pairs by volume (TOP_N_PAIRS = {args.top_n}).\n")
        else:
            print(f"📊 Running full dataset ({len(df_pairs):,} pairs) because TOP_N_PAIRS = 0.\n")

    # ====================== OUTPUT FILENAME (now includes months) ======================
    output_csv = args.input_csv.replace('volume', f'backtester_m{args.backtest_months}').replace('_sample', '')
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
                backtest_months=args.backtest_months,      # ← NEW: passed here
                target_weight_a=args.target_weight_a,
                fee_rate=args.fee_rate
            )

            result_row = row.to_dict().copy()
            result_row.update(metrics)
            results_list.append(result_row)

        results_df = pd.DataFrame(results_list)

        if 'rebalances' in results_df.columns and not results_df.empty:
            # SIMPLE SORT: everything ordered by rebalance count (highest first)
            results_df = results_df.sort_values(
                by='rebalances',
                ascending=False
            ).reset_index(drop=True)

            results_df.insert(0, 'rank', range(1, len(results_df) + 1))

            p20 = results_df['rebalances'].quantile(0.20)
            p80 = results_df['rebalances'].quantile(0.80)

            print(f"\n📊 Rebalance Percentiles (for reference):")
            print(f"   20th percentile : {p20:,.0f}")
            print(f"   80th percentile : {p80:,.0f}")
            print(f"   → All {len(results_df):,} pairs sorted purely by rebalance count (highest → lowest)")

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
    print("   • Just edit TOP_N_PAIRS or BACKTEST_MONTHS at the top of the file!")
    print("   • Or override with --top-n 15 --backtest-months 6 on the command line")
    print("   • Use --max-pairs 50 for quick testing")
    print("   • The chart is always generated at the end (pure visual reference)")
