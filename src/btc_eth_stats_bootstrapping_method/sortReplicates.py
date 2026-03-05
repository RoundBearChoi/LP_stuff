# sortReplicates.py

from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save


def sort_reps(asset1: str, asset2: str) -> None:
    print('')
    print(' --- sorting replicates --- ')

    df = _load(f'{asset1}_{asset2}_replicates.csv', ['replicate_index', 'block_index', 'date', f'{asset1}_{asset2}_price', 'change_pct'])

    # sort each replicate by change_pct
    df_sorted = df.sort_values(by=['replicate_index', 'change_pct'], ascending=[True, True])

    # drop block_index if present and save
    if 'block_index' in df_sorted.columns:
        df_sorted = df_sorted.drop(columns=['block_index'])

    df_sorted = df_sorted.reset_index(drop=True)

    print(f"total rows: {len(df_sorted)}")
    print(f"unique replicates: {df_sorted['replicate_index'].nunique()}")
    
    _save(df_sorted, f'{asset1}_{asset2}_replicates_ordered.csv')


if __name__ == "__main__":
    sort_reps("btc", "eth")
