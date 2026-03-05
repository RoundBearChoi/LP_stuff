# saveCSV.py

import os
import pandas as pd
from typing import Optional

def save_to_file(
    df: pd.DataFrame,
    fileName: str,
    index: bool = False,  # Set to True if you want to save the DataFrame index as a column
    encoding: str = 'utf-8',
    **kwargs
) -> None:
    # Get the directory where this script is located
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    
    # Create path to '../data' relative to the script
    #dataDir = os.path.join(scriptDir, '..', 'data')
    dataDir = scriptDir # just save to same folder as script

    # Build full file path and normalize it (also force lowercase filename)
    filePath = os.path.join(dataDir, fileName)
    #filePath = os.path.abspath(filePath.lower())
    
    # Create the data directory if it doesn't exist
    os.makedirs(dataDir, exist_ok=True)
    
    # Write to CSV
    df.to_csv(filePath, index=index, encoding=encoding, **kwargs)
    
    print(f'DataFrame saved to: {filePath}')
