#loadCSV.py

import os
import pandas as pd


def get_data_dir() -> str:
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    #dataDir = os.path.join(scriptDir, '..', 'data')
    dataDir = scriptDir #just put in the same folder as script..
    return os.path.abspath(dataDir)


def load_from_file(fileName: str, expectedCols: list[str]) -> pd.DataFrame:
    dataDir = get_data_dir()
    filePath = os.path.join(dataDir, fileName)
    filePath = os.path.abspath(filePath)

    print('')
    print(f'attempting to load: {filePath}')

    if not os.path.exists(filePath):
        print(f'file not found')
        #print(f'returning empty DataFrame with expected columns: {expectedCols}')
        return pd.DataFrame(columns=expectedCols)
    
    else:
        print(f'file found')

    df = pd.read_csv(filePath)

    missing = [col for col in expectedCols if col not in df.columns]
    
    if missing:
        raise ValueError(f'missing expected column(s): {missing}')
    else:
        print(f'matching columns {expectedCols}')

    return df
