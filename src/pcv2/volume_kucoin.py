import requests
import json
from typing import List, Dict, Optional

def get_kucoin_top_volume(
    limit: int = 100,
    min_vol_value: float = 500_000.0
) -> List[Dict]:
    """
    Fetch top N spot pairs on KuCoin by 24h USD quote volume.
    Returns list of dicts with key fields for your triggers.
    """
    url = "https://api.kucoin.com/api/v1/market/allTickers"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        tickers = response.json()["data"]["ticker"]
    except Exception as e:
        print(f"KuCoin API error: {e}")
        return []
    
    # Sort by volValue (USD turnover) descending
    sorted_tickers = sorted(
        tickers,
        key=lambda x: float(x.get("volValue", 0)),
        reverse=True
    )
    
    top = []
    for item in sorted_tickers:
        quote_vol = float(item.get("volValue", 0))
        if quote_vol < min_vol_value:
            continue
            
        top.append({
            "rank": len(top) + 1,
            "symbol": item["symbol"],           # e.g. "BTC-USDT"
            "quote_volume_usd": round(quote_vol, 2),
            "base_volume": float(item["vol"]),
            "price_change_percent": float(item.get("changeRate", 0)) * 100,
            "last_price": float(item["last"]),
            "high_price": float(item.get("high", 0)),
            "low_price": float(item.get("low", 0))
        })
        
        if len(top) >= limit:
            break
    
    return top

def print_top_preview(top_list: List[Dict], exchange: str = "KuCoin"):
    print(f"\n=== {exchange} TOP 10 by 24h USD Volume (of top {len(top_list)}) ===")
    print(f"{'Rank':<4} {'Symbol':<14} {'Volume (USD)':<18} {'24h %':<8} {'Last Price':<12}")
    print("-" * 72)
    for item in top_list[:10]:
        print(f"{item['rank']:<4} {item['symbol']:<14} "
              f"${item['quote_volume_usd']:,.0f} "
              f"{item['price_change_percent']:>+7.2f}% "
              f"${item['last_price']:<12}")

# ====================== EXAMPLE USAGE ======================
if __name__ == "__main__":
    top_100 = get_kucoin_top_volume(limit=100, min_vol_value=500_000)
    
    print_top_preview(top_100, "KuCoin")
    
    # Example: save full list for your bot
    with open("kucoin_top100.json", "w") as f:
        json.dump(top_100, f, indent=2)
    
    # Example trigger hook:
    # for token in top_100:
    #     if abs(token["price_change_percent"]) > 12 and token["quote_volume_usd"] > 3_000_000:
    #         print(f"🔥 VOLATILITY TRIGGER: {token['symbol']}")
