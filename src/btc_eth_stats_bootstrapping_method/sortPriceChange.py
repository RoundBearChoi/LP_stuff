# sortPriceChange.py

from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def sort_price_change(asset1: str, asset2: str) -> None:
    print('')
    print(' --- sorting price change --- ')
    
    df = _load(f'{asset1}_{asset2}_price_change.csv', ['date', 'ratio', 'change_pct'])

    print(f'sorting {len(df)} rows..')

    df_sorted = df.sort_values(by='change_pct', ascending=True)
  
    _save(df_sorted, f'{asset1}_{asset2}_price_change_ordered.csv')


if __name__ == '__main__':
    sort_price_change('btc', 'eth')
