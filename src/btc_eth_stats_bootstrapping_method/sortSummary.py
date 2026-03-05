# sortSummary.py

import pandas as pd
from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def sort_upper_lower(asset1: str, asset2: str) -> None:
    print('')
    print(' --- sorting upper lower results --- ')

    df = _load(f'{asset1}_{asset2}_upper_lower_summary.csv', ['replicate_index', 'lower_5th_pct', 'upper_95th_pct'])

    # sort lower
    df_lower = (
        df.sort_values(by='lower_5th_pct', ascending=True)
          .reset_index(drop=True)
          .drop(columns=['upper_95th_pct'])  # Remove upper column from lower sorted file
    )

    print('')
    print(df_lower)

    print('')
    _save(df_lower, f'{asset1}_{asset2}_lower_ordered.csv')

    # sort upper
    df_upper = (
        df.sort_values(by='upper_95th_pct', ascending=True)
        .reset_index(drop=True)
        .drop(columns=['lower_5th_pct'])
    )

    print('')
    print(df_upper)

    print('')
    _save(df_upper, f'{asset1}_{asset2}_upper_ordered.csv')


if __name__ == '__main__':
    sort_upper_lower('btc', 'eth')
