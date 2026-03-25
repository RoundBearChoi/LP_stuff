import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

class VolatilityHarvestingBacktester:
    def __init__(self, 
                 csv_path='top300_hourly_18months_combined.csv',
                 asset_a='XVG',
                 asset_b='BTC',
                 target_weight_a=0.50,
                 outer_buffer=0.05,
                 inner_rebalance_dev=0.025,
                 initial_capital=2000.0,
                 fee_rate=0.01,
                 backtest_months=18):
        
        self.csv_path = csv_path
        self.asset_a = asset_a
        self.asset_b = asset_b
        self.target_weight_a = target_weight_a
        self.outer_buffer = outer_buffer
        self.inner_rebalance_dev = inner_rebalance_dev
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.backtest_months = backtest_months
        
        # ====================== DYNAMIC OUTPUT FILENAME ======================
        # Identical logic to the original script
        if self.backtest_months is None:
            self.months_str = "full"
        else:
            self.months_str = f"{self.backtest_months}months"
        
        self.output_filename = f"volatility_harvesting_{self.asset_a}_{self.asset_b}_{self.months_str}.png"
        # =====================================================================
        
        # Pre-compute column names once (used throughout)
        self.col_a = f'{self.asset_a.lower()}_close'
        self.col_b = f'{self.asset_b.lower()}_close'
        
        # Will be populated during run
        self.data = None
        self.portfolio = None
        self.metrics = None

    def load_and_prepare_data(self):
        """Load the combined hourly dataset and prepare the two-asset DataFrame.
        
        This method is identical to the original script's loading + slicing + joining logic.
        Prints are preserved verbatim for exact behavioral match.
        """
        df = pd.read_csv(self.csv_path)
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.sort_values('datetime').set_index('datetime')

        # Optional slice to the most recent N months
        if self.backtest_months is not None:
            end_dt = df.index.max()
            start_dt = end_dt - pd.DateOffset(months=self.backtest_months)
            df = df[df.index >= start_dt]
            print(f"✅ Backtesting only the last {self.backtest_months} months: {df.index.min()} → {df.index.max()}")
        else:
            print(f"✅ Using full dataset: {df.index.min()} → {df.index.max()}")

        # Extract the two assets dynamically
        a = df[df['symbol'] == self.asset_a][['close']].rename(columns={'close': self.col_a})
        b = df[df['symbol'] == self.asset_b][['close']].rename(columns={'close': self.col_b})

        # Align on exact same timestamps
        self.data = a.join(b, how='inner').dropna()

        print(f"Data range after filtering: {self.data.index[0]} → {self.data.index[-1]}")
        print(f"Total bars: {len(self.data):,}")

    def run_backtest(self):
        """Run the full volatility-harvesting backtest.
        
        This is the main entry point. It executes every original section in the exact same order
        and with identical logic, prints, calculations, and file output.
        """
        self.load_and_prepare_data()
        
        # ====================== BACKTEST ENGINE ======================
        self.portfolio = pd.DataFrame(index=self.data.index)
        self.portfolio[self.col_a] = self.data[self.col_a]
        self.portfolio[self.col_b] = self.data[self.col_b]

        # Initial allocation
        price_a_0 = self.data[self.col_a].iloc[0]
        price_b_0 = self.data[self.col_b].iloc[0]
        shares_a = (self.initial_capital * self.target_weight_a) / price_a_0
        shares_b = (self.initial_capital * (1 - self.target_weight_a)) / price_b_0

        # Tracking columns
        self.portfolio['a_value'] = np.nan
        self.portfolio['b_value'] = np.nan
        self.portfolio['total_value'] = np.nan
        self.portfolio['weight_a'] = np.nan
        self.portfolio['trade'] = 0.0
        self.portfolio['rebalance'] = False

        for ts in self.portfolio.index:
            a_val = shares_a * self.portfolio.loc[ts, self.col_a]
            b_val = shares_b * self.portfolio.loc[ts, self.col_b]
            total = a_val + b_val
            
            weight_a = a_val / total if total > 0 else self.target_weight_a
            
            self.portfolio.loc[ts, 'a_value'] = a_val
            self.portfolio.loc[ts, 'b_value'] = b_val
            self.portfolio.loc[ts, 'total_value'] = total
            self.portfolio.loc[ts, 'weight_a'] = weight_a
            
            deviation = weight_a - self.target_weight_a
            if abs(deviation) > self.outer_buffer:
                new_target = self.target_weight_a + np.sign(deviation) * self.inner_rebalance_dev
                target_a_val = new_target * total
                target_b_val = (1 - new_target) * total
                trade_usd = abs(target_a_val - a_val)
                fee = trade_usd * self.fee_rate
                trade_usd_net = trade_usd - fee
                
                if target_a_val > a_val:  # buy A, sell B
                    shares_a += trade_usd_net / self.portfolio.loc[ts, self.col_a]
                    shares_b -= trade_usd / self.portfolio.loc[ts, self.col_b]
                else:                     # sell A, buy B
                    shares_a -= trade_usd / self.portfolio.loc[ts, self.col_a]
                    shares_b += trade_usd_net / self.portfolio.loc[ts, self.col_b]
                
                self.portfolio.loc[ts, 'trade'] = trade_usd
                self.portfolio.loc[ts, 'rebalance'] = True
                
                # Recalculate after trade
                a_val = shares_a * self.portfolio.loc[ts, self.col_a]
                b_val = shares_b * self.portfolio.loc[ts, self.col_b]
                total = a_val + b_val
                self.portfolio.loc[ts, 'total_value'] = total
                self.portfolio.loc[ts, 'weight_a'] = a_val / total

        # ====================== BENCHMARKS ======================
        bh_shares_a = (self.initial_capital * self.target_weight_a) / self.data[self.col_a].iloc[0]
        bh_shares_b = (self.initial_capital * (1 - self.target_weight_a)) / self.data[self.col_b].iloc[0]
        self.portfolio['bh_value'] = bh_shares_a * self.portfolio[self.col_a] + bh_shares_b * self.portfolio[self.col_b]

        self.portfolio['a_only'] = self.initial_capital * (self.portfolio[self.col_a] / self.data[self.col_a].iloc[0])
        self.portfolio['b_only'] = self.initial_capital * (self.portfolio[self.col_b] / self.data[self.col_b].iloc[0])

        # ====================== PURCHASING POWER EQUIVALENTS ======================
        self._print_purchasing_power()

        # ====================== PERFORMANCE METRICS ======================
        self._calculate_metrics()
        self._print_results()

        # ====================== PLOTS ======================
        self.plot_results()

    def _print_purchasing_power(self):
        """Print starting and ending purchasing-power equivalents (identical to original)."""
        start_time      = self.data.index[0]
        end_time        = self.data.index[-1]
        start_price_a   = self.data[self.col_a].iloc[0]
        start_price_b   = self.data[self.col_b].iloc[0]
        end_price_a     = self.data[self.col_a].iloc[-1]
        end_price_b     = self.data[self.col_b].iloc[-1]

        start_a_eq = self.initial_capital / start_price_a
        start_b_eq = self.initial_capital / start_price_b

        print(f"\nStarting purchasing power equivalents ({start_time}):")
        print(f"  ASSET_A ({self.asset_a}): {start_a_eq:,.4f} {self.asset_a}")
        print(f"  ASSET_B ({self.asset_b}): {start_b_eq:,.4f} {self.asset_b}")

        final_strategy_value = self.portfolio['total_value'].iloc[-1]
        final_btc_eq = final_strategy_value / end_price_b   # keep "btc" naming for clarity (original comment)
        final_a_eq   = final_strategy_value / end_price_a

        print(f"\nLatest purchasing power equivalents ({end_time}):")
        print(f"  ASSET_A ({self.asset_a}): {final_a_eq:,.2f} {self.asset_a}")
        print(f"  ASSET_B ({self.asset_b}): {final_btc_eq:,.4f} {self.asset_b}")

    def _calculate_metrics(self):
        """Compute all performance metrics (CAGR, Max DD, Vol, Sharpe, etc.) exactly as original."""
        def cagr(series):
            days = (series.index[-1] - series.index[0]).days
            return (series.iloc[-1] / series.iloc[0]) ** (365.25 / days) - 1

        def max_dd(series):
            peak = series.cummax()
            drawdown = (series - peak) / peak
            return drawdown.min()

        self.metrics = pd.DataFrame(index=['Strategy', f'{self.asset_a}_100%', f'{self.asset_b}_100%', 'BuyHold_50/50'])
        
        for col, name in [('total_value', 'Strategy'),
                          ('a_only', f'{self.asset_a}_100%'),
                          ('b_only', f'{self.asset_b}_100%'),
                          ('bh_value', 'BuyHold_50/50')]:
            s = self.portfolio[col]
            final_val = s.iloc[-1]
            
            # Re-compute final equivalents (identical math to original)
            end_price_a = self.data[self.col_a].iloc[-1]
            end_price_b = self.data[self.col_b].iloc[-1]
            final_a_eq = final_val / end_price_a
            final_b_eq = final_val / end_price_b
            
            self.metrics.loc[name, 'Final Value (USD)'] = final_val
            self.metrics.loc[name, 'Total Return (%)'] = ((final_val / self.initial_capital) - 1) * 100
            self.metrics.loc[name, 'CAGR (%)'] = cagr(s) * 100
            self.metrics.loc[name, 'Max DD (%)'] = max_dd(s) * 100
            self.metrics.loc[name, 'Vol (ann.)'] = s.pct_change().std() * np.sqrt(365.25 * 24) * 100
            self.metrics.loc[name, 'Sharpe (rf=0)'] = (s.pct_change().mean() / s.pct_change().std()) * np.sqrt(365.25 * 24)
            
            # Purchasing-power growth columns (original used pre-computed start values; we recompute inline for exact equivalence)
            start_a_eq = self.initial_capital / self.data[self.col_a].iloc[0]
            start_b_eq = self.initial_capital / self.data[self.col_b].iloc[0]
            self.metrics.loc[name, f'Final {self.asset_b} equiv'] = final_b_eq
            self.metrics.loc[name, f'{self.asset_b} equiv growth (%)'] = ((final_b_eq / start_b_eq) - 1) * 100
            self.metrics.loc[name, f'Final {self.asset_a} equiv'] = final_a_eq
            self.metrics.loc[name, f'{self.asset_a} equiv growth (%)'] = ((final_a_eq / start_a_eq) - 1) * 100

    def _print_results(self):
        """Print metrics table and rebalance summary (exact same formatting as original)."""
        print("\n=== BACKTEST RESULTS ===")
        print(self.metrics.round(2))

        print(f"\nRebalances triggered: {self.portfolio['rebalance'].sum():,} "
              f"({self.portfolio['trade'].sum():,.0f} USD total volume traded)")

    def plot_results(self):
        """Generate the three-panel plot and save it with the exact same filename & DPI."""
        fig, axs = plt.subplots(3, 1, figsize=(14, 10), height_ratios=[3, 2, 1])

        axs[0].plot(self.portfolio['total_value'], label='Strategy (trigger + partial)', linewidth=2)
        axs[0].plot(self.portfolio['bh_value'], label='Buy-&-Hold 50/50', alpha=0.7)
        axs[0].plot(self.portfolio['a_only'], label=f'100% {self.asset_a}', alpha=0.5)
        axs[0].plot(self.portfolio['b_only'], label=f'100% {self.asset_b}', alpha=0.5)
        axs[0].set_title(f'Portfolio Value – Volatility Harvesting Backtest ({self.asset_a}-{self.asset_b}, {self.months_str})')
        axs[0].set_ylabel('USD')
        axs[0].legend()
        axs[0].grid(True)

        axs[1].plot(self.portfolio['weight_a'], label=f'{self.asset_a} Weight', color='purple')
        axs[1].axhline(self.target_weight_a, color='black', linestyle='--', label='Target')
        axs[1].axhline(self.target_weight_a + self.outer_buffer, color='red', linestyle=':', label=f'+{self.outer_buffer*100}% trigger')
        axs[1].axhline(self.target_weight_a - self.outer_buffer, color='red', linestyle=':')
        axs[1].axhline(self.target_weight_a + self.inner_rebalance_dev, color='orange', linestyle='-.', label=f'±{self.inner_rebalance_dev*100}% partial')
        axs[1].axhline(self.target_weight_a - self.inner_rebalance_dev, color='orange', linestyle='-.')
        axs[1].set_ylabel(f'{self.asset_a} Weight')
        axs[1].legend()
        axs[1].grid(True)

        rebal_dates = self.portfolio[self.portfolio['rebalance']].index
        axs[2].vlines(rebal_dates, ymin=0, ymax=self.portfolio['trade'].max()*1.1 if not self.portfolio['trade'].empty else 1,
                      color='red', alpha=0.6, linewidth=1, label='Rebalance')
        axs[2].set_ylabel('Trade Size (USD)')
        axs[2].legend()
        axs[2].grid(True)

        plt.tight_layout()
        plt.savefig(self.output_filename, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"✅ Chart saved as '{self.output_filename}' (DPI 150)")


# ====================== USAGE ======================
# The script now runs exactly as the original when executed directly.
if __name__ == "__main__":
    backtester = VolatilityHarvestingBacktester()
    backtester.run_backtest()
