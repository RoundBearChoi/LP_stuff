#getPriceRatio.py

import pandas as pd
from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def get_price_ratio(asset1='btc', asset2='eth'):
    asset1 = asset1.lower()
    asset2 = asset2.lower()
    
    print("")
    print(f" --- calculating {asset1}/{asset2} price ratio ---")

    df1 = _load(f'{asset1}_daily_closing.csv', ['date', f'{asset1}_closing_price_usd'])
    df2 = _load(f'{asset2}_daily_closing.csv', ['date', f'{asset2}_closing_price_usd'])
   
    print('')
    print(df1)

    print('')
    print(df2)

    # second column is the price (first is 'date')
    price_col1 = df1.columns[1]
    price_col2 = df2.columns[1]
    
    # set date as index
    df1 = df1.set_index('date')
    df2 = df2.set_index('date')
    
    # extract only the price series
    price_series1 = df1[price_col1]
    price_series2 = df2[price_col2]
    
    # combine with inner join (only common dates)
    combined = pd.concat([price_series1, price_series2], axis=1, join='inner')

    # rename the columns to the assets for clarity (removes the longer original names)
    combined.columns = [asset1, asset2]
    
    # calculate price ratio
    combined['ratio'] = combined[asset1] / combined[asset2]

    # save to CSV
    result_df = combined.reset_index()[['date', asset1, asset2, 'ratio']]

    print('')
    print(result_df)

    _save(result_df, f'{asset1}_{asset2}_price.csv') 


if __name__ == '__main__':
    get_price_ratio('btc', 'eth')
