# drawGraphOnHistoricPrice.py

import os
import pandas as pd
import matplotlib.pyplot as plt
import datetime
from loadCSV import load_from_file as _load
from loadCSV import get_data_dir as _getDataDir


def draw_graph(asset1: str, asset2: str) -> None:
    print('')
    print(' --- drawing graph on historic price --- ')

    df = _load(f'{asset1}_{asset2}_price_change_ordered.csv', ['date', 'ratio', 'change_pct'])

    # create bar graph
    plt.figure(figsize=(14, 7))
    bars = plt.bar(range(len(df)), df['change_pct'], color='skyblue', edgecolor='navy', linewidth=0.5)
    
    # highlight negative and positive bars
    for bar in bars:
        if bar.get_height() < 0:
            bar.set_color('salmon')
    
    plt.title(f'{asset1} vs {asset2} - daily price change %', fontsize=16)
    plt.ylabel('price change %', fontsize=12)
    plt.axhline(0, color='black', linewidth=1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # get current date and time
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # title with current date/time
    plt.title(f'{asset1.upper()} vs {asset2.upper()} - daily price change % - {current_time}', fontsize=15)
    
    plt.ylabel('price Change %', fontsize=12)
    plt.axhline(0, color='black', linewidth=1)
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # add percentile lines
    p5 = df['change_pct'].quantile(0.05)
    p95 = df['change_pct'].quantile(0.95)
    plt.axhline(p5, color='red', linestyle='--', label='5th percentile')
    plt.axhline(p95, color='red', linestyle='--', label='95th percentile')
    
    # add text labels next to the lines (placed at the right edge of the plot)
    plt.text(len(df) - 0.5, p5, f'  5th percentile: {p5:+.3f}%', 
             va='center', ha='left', color='red', fontsize=10, fontweight='bold',
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=3))

    plt.text(len(df) - 0.5, p95, f'  95th percentile: {p95:+.3f}%', 
             va='center', ha='left', color='red', fontsize=10, fontweight='bold',
             bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=3))

    plt.tight_layout()

    graphPath = os.path.join(_getDataDir(), f'{asset1}_{asset2}_change_pct_bargraph.png')
    plt.savefig(graphPath)
    print('')
    print(f"graph saved to: {os.path.abspath(graphPath)}")
    
    plt.show(block=False)


if __name__ == '__main__':
    draw_graph('btc', 'eth')
