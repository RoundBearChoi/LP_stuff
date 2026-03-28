import requests
import json
from typing import List, Dict

def get_kucoin_top_volume(limit: int = 20, min_vol_value: float = 1_000_000) -> List[Dict]:
    url = "https://api.kucoin.com/api/v1/market/allTickers"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    tickers = response.json()["data"]["ticker"]
    
    # Sort by volValue (quote volume) descending
    sorted_tickers = sorted(
        tickers,
        key=lambda x: float(x.get("volValue", 0)),
        reverse=True
    )
    
    top = []
    for item in sorted_tickers:
        if float(item.get("volValue", 0)) < min_vol_value:
            continue
        top.append({
            "symbol": item["symbol"],
            "quoteVolume": float(item["volValue"]),   # this is the USD turnover
            "volume": float(item["vol"]),
            "changeRate": float(item.get("changeRate", 0)),
            "lastPrice": float(item["last"])
        })
        if len(top) >= limit:
            break
    return top

# Example usage
if __name__ == "__main__":
    top_tokens = get_kucoin_top_volume(limit=10)
    print(json.dumps(top_tokens, indent=2))
