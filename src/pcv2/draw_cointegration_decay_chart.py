import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
import os
import matplotlib.dates as mdates
from cointegration_engine import compute_cointegration
from config import DEFAULT_CHART_MONTHS, DEFAULT_CSV_FILE, DEFAULT_COINTEGRATION_METHOD


class CointegrationDecayChart:
    """Simplified p-value decay scan:
    - Top: normalized prices over full chart_months
    - Bottom: cointegration p-value for every lookback from 1 month → chart_months
    No rolling windows, no spread/z-score — pure & clean.
    """

    def __init__(self, sym1: str, sym2: str, csv_file: str = None,
                 chart_months: int = None):
        self.sym1 = sym1.upper()
        self.sym2 = sym2.upper()
        self.csv_file = csv_file or DEFAULT_CSV_FILE
        self.chart_months = chart_months or DEFAULT_CHART_MONTHS

    def _load_data(self):
        if not os.path.exists(self.csv_file):
            print(f"❌ File '{self.csv_file}' not found!")
            sys.exit(1)

        df = pd.read_csv(self.csv_file, parse_dates=['datetime'])
        end_date = df['datetime'].max()

        days_back = int(self.chart_months * 30.437)
        start_date = end_date - pd.Timedelta(days=days_back)
        df = df[df['datetime'] >= start_date].copy()

        print(f"Loaded last {self.chart_months} months: "
              f"{df['datetime'].min().date()} → {end_date.date()}")

        df_pair = df[df['symbol'].isin([self.sym1, self.sym2])].copy()
        pivot = df_pair.pivot(index='datetime', columns='symbol', values='close').dropna()

        if self.sym1 not in pivot.columns or self.sym2 not in pivot.columns:
            print(f"❌ Symbols not found. Available: {list(pivot.columns)}")
            sys.exit(1)

        p1 = pivot[self.sym1]
        p2 = pivot[self.sym2]
        print(f"Data for {self.sym1}/{self.sym2}: {len(p1):,} hourly bars")
        return p1, p2

    def _compute_lookback_pvalues(self, p1_full: pd.Series, p2_full: pd.Series):
        results = []
        method_name = DEFAULT_COINTEGRATION_METHOD.value

        print(f"\nComputing cointegration p-values (1–{self.chart_months} months) "
              f"using {method_name}...")

        for m in range(1, self.chart_months + 1):
            hours_back = int(m * 30.437 * 24)
            p1_win = p1_full.iloc[-hours_back:]
            p2_win = p2_full.iloc[-hours_back:]

            if len(p1_win) < 200:
                print(f"  ⚠️ {m:2d} months: too few bars ({len(p1_win)}), skipped")
                continue

            eg = compute_cointegration(p1_win, p2_win, method=DEFAULT_COINTEGRATION_METHOD)
            results.append({
                'months': m,
                'p_value': eg.p_value,
                'beta': eg.beta,
                'half_life': getattr(eg, 'half_life_days', None)
            })

            if m % 6 == 0 or m == 1 or m == self.chart_months:
                status = "✓ Significant" if eg.p_value < 0.05 else "× Not significant"
                print(f"  → {m:2d} months: p = {eg.p_value:.5f}  {status}")

        return results

    def generate(self):
        p1, p2 = self._load_data()
        lookback_results = self._compute_lookback_pvalues(p1, p2)

        # Prepare plot data
        months = [r['months'] for r in lookback_results]
        pvals = [r['p_value'] for r in lookback_results]

        # Normalized prices (full period)
        norm1 = p1 / p1.iloc[0] * 100
        norm2 = p2 / p2.iloc[0] * 100

        # === FIGURE ===
        fig, axs = plt.subplots(2, 1, figsize=(14, 11),
                                gridspec_kw={'hspace': 0.38})

        # ==================== CHART 1: NORMALIZED PRICES ====================
        axs[0].plot(norm1.index, norm1, label=self.sym1, linewidth=2.2)
        axs[0].plot(norm2.index, norm2, label=self.sym2, linewidth=2.2)
        axs[0].set_title(f"1. Normalized Prices — {self.sym1} vs {self.sym2}")
        axs[0].legend(loc='upper left')
        axs[0].grid(True, alpha=0.3)

        # Nice summary box
        full = lookback_results[-1]
        method_display = DEFAULT_COINTEGRATION_METHOD.value.replace('_', ' ').title()
        axs[0].text(0.02, 0.82,
                    f"Method: {method_display}\n"
                    f"Full {self.chart_months}m p-value = {full['p_value']:.5f}\n"
                    f"Beta = {full['beta']:.4f}\n"
                    f"Half-life ≈ {full.get('half_life', 'N/A'):.1f} days",
                    transform=axs[0].transAxes,
                    fontsize=12.5, ha='left', va='top', fontweight='bold',
                    bbox=dict(boxstyle="round,pad=1", facecolor="#e6f3ff",
                              edgecolor='navy', alpha=0.95))

        # ==================== CHART 2: P-VALUE SWEEP ====================
        ax = axs[1]
        ax.plot(months, pvals, marker='o', markersize=5, linewidth=2.8,
                color='purple', label='Cointegration p-value')

        ax.axhline(0.05, color='red', linestyle='--', linewidth=2.2,
                   label='p = 0.05 threshold')
        ax.axhline(0.01, color='darkgreen', linestyle='--', alpha=0.75)

        ax.fill_between(months, 0, 0.05,
                        where=np.array(pvals) < 0.05,
                        color='lightgreen', alpha=0.45,
                        label='Cointegrated')

        ax.set_title(f"2. Cointegration p-value by Lookback Period (1–{self.chart_months} months)")
        ax.set_xlabel("Lookback Period (months)")
        ax.set_ylabel("p-value")
        ax.set_ylim(0, 1.05)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=11)
        ax.set_xticks(range(0, self.chart_months + 1, max(1, self.chart_months // 8)))

        # ==================== SAVE (NEW FILENAME FORMAT) ====================
        fig.suptitle(f"COINTEGRATION P-VALUE DECAY SCAN — {self.sym1} vs {self.sym2}\n"
                     f"Method: {method_display} | Last {self.chart_months} months",
                     fontsize=15.5, y=0.96)

        output_file = f"cointegration_{self.sym1}_{self.sym2}_{DEFAULT_COINTEGRATION_METHOD.value}_{self.chart_months}m_pvalue_scan.png"

        plt.savefig(output_file, dpi=200, bbox_inches='tight')
        plt.close(fig)

        print(f"\n✅ Saved: {output_file}")
        print(f"   Full-period ({self.chart_months}m) p-value: {full['p_value']:.5f}")


if __name__ == "__main__":
    csv_file = None
    sym1 = "ETH"
    sym2 = "BTC"
    chart_months = DEFAULT_CHART_MONTHS

    if len(sys.argv) > 1:
        args = sys.argv[1:]
        if args and args[-1].isdigit():
            chart_months = int(args.pop())

        if len(args) == 0:
            print(f"⚡ No symbols provided → default {sym1}/{sym2}")
        elif len(args) == 2:
            sym1 = args[0].upper()
            sym2 = args[1].upper()
        elif len(args) == 3:
            csv_file = args[0]
            sym1 = args[1].upper()
            sym2 = args[2].upper()
        else:
            print(f"Usage: python draw_cointegration_decay_chart.py [CSV_FILE] SYM1 SYM2 [chart_months]")
            print("Example: python draw_cointegration_decay_chart.py ETH SOL 12")
            sys.exit(1)

    chart = CointegrationDecayChart(sym1, sym2, csv_file, chart_months)
    chart.generate()
