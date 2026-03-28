import requests
import json
from typing import List, Dict, Optional

def get_mexc_top_volume(
    limit: int = 100,
    min_quote_vol: float = 500_000.0
) -> List[Dict]:
    """
    Fetch top N spot pairs on MEXC by 24h USD quote volume.
    Returns list of dicts with key fields for your triggers.
    """
    url = "https://api.mexc.com/api/v3/ticker/24hr"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data: List[Dict] = response.json()
    except Exception as e:
        print(f"MEXC API error: {e}")
        return []
    
    # Sort by quoteVolume (USD turnover) descending
    sorted_data = sorted(
        data,
        key=lambda x: float(x.get("quoteVolume", 0)),
        reverse=True
    )
    
    top = []
    for item in sorted_data:
        quote_vol = float(item.get("quoteVolume", 0))
        if quote_vol < min_quote_vol:
            continue
            
        top.append({
            "rank": len(top) + 1,
            "symbol": item["symbol"],
            "quote_volume_usd": round(quote_vol, 2),
            "base_volume": float(item["volume"]),
            "price_change_percent": float(item.get("priceChangePercent", 0)),
            "last_price": float(item["lastPrice"]),
            "high_price": float(item["highPrice"]),
            "low_price": float(item["lowPrice"])
        })
        
        if len(top) >= limit:
            break
    
    return top

def print_top_preview(top_list: List[Dict], exchange: str = "MEXC"):
    print(f"\n=== {exchange} TOP 10 by 24h USD Volume (of top {len(top_list)}) ===")
    print(f"{'Rank':<4} {'Symbol':<12} {'Volume (USD)':<18} {'24h %':<8} {'Last Price':<12}")
    print("-" * 70)
    for item in top_list[:10]:
        print(f"{item['rank']:<4} {item['symbol']:<12} "
              f"${item['quote_volume_usd']:,.0f} "
              f"{item['price_change_percent']:>+7.2f}% "
              f"${item['last_price']:<12}")

# ====================== EXAMPLE USAGE ======================
if __name__ == "__main__":
    top_100 = get_mexc_top_volume(limit=100, min_quote_vol=500_000)
    
    print_top_preview(top_100, "MEXC")
    
    # Example: save full list for your bot
    with open("mexc_top100.json", "w") as f:
        json.dump(top_100, f, indent=2)
    
    # Example trigger hook:
    # for token in top_100:
    #     if token["price_change_percent"] > 15 and token["quote_volume_usd"] > 5_000_000:
    #         print(f"🚀 VOLATILITY TRIGGER: {token['symbol']}")
