import pandas as pd
from loadCSV import load_from_file as _load 
from saveCSV import save_to_file as _save


def get_price_change(asset1: str, asset2: str) -> None:
    asset1 = asset1.lower()
    asset2 = asset2.lower()

    print('')
    print(f' --- calculating {asset1}_{asset2} price change --- ')
    
    df = _load(f'{asset1}_{asset2}_price.csv', ['date', asset1, asset2, 'ratio'])

    # calculate percentage change in the ratio from previous day
    df['change_pct'] = df['ratio'].pct_change() * 100
    
    # select and reorder columns for output
    result_df = df[['date', 'ratio', 'change_pct']].copy()
    
    # optional: round for cleaner output
    result_df['ratio'] = result_df['ratio'].round(12)
    result_df['change_pct'] = result_df['change_pct'].round(8)

    # remove day 0 and save
    result_df = result_df.iloc[1:].reset_index(drop=True)
    print(f"{len(result_df)} rows after removing day 0")
   
    _save(result_df, f'{asset1}_{asset2}_price_change.csv') 


if __name__ == '__main__':
    get_price_change('btc', 'eth')
