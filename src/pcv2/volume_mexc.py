import requests
import json
from typing import List, Dict

def get_mexc_top_volume(limit: int = 20, min_quote_vol: float = 1_000_000) -> List[Dict]:
    url = "https://api.mexc.com/api/v3/ticker/24hr"   # no symbol = ALL pairs
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data: List[Dict] = response.json()
    
    # Sort by quoteVolume (USD turnover) descending
    sorted_data = sorted(
        data,
        key=lambda x: float(x.get("quoteVolume", 0)),
        reverse=True
    )
    
    top = []
    for item in sorted_data:
        if float(item.get("quoteVolume", 0)) < min_quote_vol:
            continue
        top.append({
            "symbol": item["symbol"],
            "quoteVolume": float(item["quoteVolume"]),
            "volume": float(item["volume"]),
            "priceChangePercent": float(item.get("priceChangePercent", 0)),
            "lastPrice": float(item["lastPrice"])
        })
        if len(top) >= limit:
            break
    return top

# Example usage
if __name__ == "__main__":
    top_tokens = get_mexc_top_volume(limit=10)
    print(json.dumps(top_tokens, indent=2))
