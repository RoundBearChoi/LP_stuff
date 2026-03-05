# drawGraphOnReplicates

import os
import pandas as pd
import matplotlib.pyplot as plt
from enum import Enum
from loadCSV import load_from_file as _load
from loadCSV import get_data_dir as _getDataDir


class GraphType(Enum):
    LOWER = 'lower'
    UPPER = 'upper'
    

def draw(asset1: str, asset2: str) -> None:
    print('')
    print(' --- drawing graphs on replicates --- ')

    df_lower = _load(f'{asset1}_{asset2}_lower_ordered.csv', ['replicate_index', 'lower_5th_pct'])
    df_upper = _load(f'{asset1}_{asset2}_upper_ordered.csv', ['replicate_index', 'upper_95th_pct'])

    proc_graph(df_lower, 'lower', asset1, asset2)
    proc_graph(df_upper, 'upper', asset1, asset2)


def proc_graph(df: pd.DataFrame, graphType: GraphType, asset1: str, asset2: str) -> None:
    # use a simple sequential x-axis (0, 1, 2, ...) since we're not using replicate_index
    x = range(len(df))

    # create the plot
    plt.figure(figsize=(12, 6))

    col = ''

    if graphType == 'lower':
        col = 'lower_5th_pct'
    elif graphType == 'upper':
        col = 'upper_95th_pct'

    plt.bar(x, df[col], color='skyblue', edgecolor='navy', alpha=0.8)
    
    # horizontal line for the median
    median_value = df[col].median()
    
    plt.axhline(y=median_value, color='red', linestyle='--', linewidth=2,
                label=f'median = {median_value:.6f}')
    
    # add lines for 2.5th percentile and 97.5th percentile
    p025 = df[col].quantile(0.025)
    p975 = df[col].quantile(0.975)
    plt.axhline(y=p025, color='orange', linestyle=':', linewidth=2,
                label=f'2.5th pct = {p025:.6f}')
    plt.axhline(y=p975, color='orange', linestyle=':', linewidth=2,
                label=f'97.5th pct = {p975:.6f}')   
    
    # add grid for better readability
    plt.grid(True, axis='y', linestyle=':', alpha=0.7)
    
    # labels and title
    plt.xlabel('ordered replicates')

    graphPath = ''

    if graphType == 'lower':
        plt.ylabel('lower 5th percentile values')
        plt.title(f'{asset1}-{asset2} lower 5th percentiles')
        graphPath = os.path.join(_getDataDir(), f'{asset1}_{asset2}_lower_5th_percentile_graph.png')
    elif graphType == 'upper':
        plt.ylabel('upper 95th percentile values')
        plt.title(f'{asset1}-{asset2} upper 5th percentiles')
        graphPath = os.path.join(_getDataDir(), f'{asset1}_{asset2}_upper_95th_percentile_graph.png')
    
    if not graphPath:
        raise ValueError('unable to set path to save graph') 
    
    plt.legend()
    plt.tight_layout()
    plt.show(block=False)

    plt.savefig(graphPath)
    print('')
    print(f"graph saved to: {os.path.abspath(graphPath)}")


if __name__ == '__main__':
    draw('btc', 'eth')
