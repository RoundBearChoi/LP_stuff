import pandas as pd
import math
import numpy as np
from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def generate_block(repIndex: int, blockIndex: int, df: pd.DataFrame, block_size: int) -> pd.DataFrame:
    # generate a random wrapped block of rows from the DataFrame.
    totalRows = len(df)
    rng = np.random.default_rng()
    randInt = rng.integers(0, totalRows)  # random starting row
    
    # wrapped indices
    indices = [(randInt + i) % totalRows for i in range(block_size)]
    
    # select rows: date, ratio, change_pct
    selected = df.iloc[indices, [0, 1, 2]].copy().reset_index(drop=True)
    selected.columns = ['date', 'ratio', 'change_pct']
    
    # add replicate and block info
    selected.insert(0, 'replicate_index', repIndex)
    selected.insert(1, 'block_index', blockIndex)
    
    return selected


def generate_replicates(asset1: str, asset2: str, n_replicates: int = 10) -> None:
    print("")
    print(" --- generating replicates ---")
    
    df = _load(f'{asset1}_{asset2}_price_change.csv', ['date', 'ratio', 'change_pct'])

    # Output setup
    price_col_name = f'{asset1}_{asset2}_price'
    #fieldnames = ['replicate_index', 'block_index', 'date', price_col_name, 'change_pct']

    # block parameters
    total_rows = len(df)
    block_size = round(math.sqrt(total_rows)) #sqrt heuristic
    block_count = math.ceil(total_rows / block_size)

    print(f"total rows: {total_rows}")
    print(f"block size: {block_size}")
    print(f"number of blocks per replicate: {block_count}")
    print(f"total replicates: {n_replicates}")

    all_replicates = []

    for rep_index in range(n_replicates):
        #print(f"generating replicate {rep_index + 1}/{n_replicates}")
        replicate_blocks = []

        for block_index in range(block_count):
            block_df = generate_block(
                repIndex=rep_index,
                blockIndex=block_index,
                df=df,
                block_size=block_size
            )
            # add the price column (same as ratio)
            block_df[price_col_name] = block_df['ratio']
            # final column order
            final_block = block_df[['replicate_index', 'block_index', 'date', price_col_name, 'change_pct']]
            replicate_blocks.append(final_block)

            #first_date = block_df['date'].iloc[0]
            #print(f"block {block_index + 1}/{block_count} starting at {first_date}")

        # combine blocks for this replicate
        replicate_df = pd.concat(replicate_blocks, ignore_index=True)
        all_replicates.append(replicate_df)

    # combine all replicates and save
    full_df = pd.concat(all_replicates, ignore_index=True)

    print(f"total rows in file: {len(full_df)}")
    print(f"rows per replicate: {len(full_df) // n_replicates}")
    
    _save(full_df, f'{asset1}_{asset2}_replicates.csv')


if __name__ == '__main__':
    generate_replicates('btc', 'eth', 10)
