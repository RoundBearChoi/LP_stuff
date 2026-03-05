# getUpperLower.py

import pandas as pd
from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def get_upper_lower(asset1: str, asset2: str) -> None:
    print('')
    print(' --- getting upper lower of replicates --- ')
    
    df = _load(f'{asset1}_{asset2}_replicates_ordered.csv', ['replicate_index', 'date', f'{asset1}_{asset2}_price', 'change_pct'])

    # group by replicate_index and calculate 5th and 95th percentiles of change_pct
    grouped = df.groupby('replicate_index')['change_pct']
    
    lower = grouped.quantile(0.05)  # 5th percentile
    upper = grouped.quantile(0.95)  # 95th percentile
    
    # combine into a summary DataFrame
    summary = pd.DataFrame({
        'lower_5th_pct': lower,
        'upper_95th_pct': upper
    }).reset_index()

    # print results and save
    print('')
    print('summary of change_pct bounds per replicate_index:')
    print(summary)
    print('')

    _save(summary, f'{asset1}_{asset2}_upper_lower_summary.csv')


if __name__ == '__main__':
    get_upper_lower('btc', 'eth')
