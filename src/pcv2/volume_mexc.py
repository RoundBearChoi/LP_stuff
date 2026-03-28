import requests
import json
from typing import List, Dict

# ========================= CONFIG =========================
CONFIG = {
    "default_limit": 200,
    "default_min_volume_usd": 100_000.0, # 24h volume in usd
    "api_timeout": 10,
    "json_filename": "mexc_top_volume.json",
    "print_top_n": 10,
}
# =========================================================

class MEXCVolumeFetcher:
    """Clean class to fetch top spot pairs on MEXC by 24h USD quote volume."""

    def __init__(self, limit: int = None, min_volume_usd: float = None):
        self.limit = limit or CONFIG["default_limit"]
        self.min_volume_usd = min_volume_usd or CONFIG["default_min_volume_usd"]
        self.timeout = CONFIG["api_timeout"]

    def get_top_volume(self) -> List[Dict]:
        """Fetch and return list of top pairs (same dict format as before)."""
        url = "https://api.mexc.com/api/v3/ticker/24hr"
        
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data: List[Dict] = response.json()
        except Exception as e:
            print(f"MEXC API error: {e}")
            return []
        
        sorted_data = sorted(
            data,
            key=lambda x: float(x.get("quoteVolume", 0)),
            reverse=True
        )
        
        top = []
        for item in sorted_data:
            quote_vol = float(item.get("quoteVolume", 0))
            if quote_vol < self.min_volume_usd:
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
            
            if len(top) >= self.limit:
                break
        
        return top

    def print_top_preview(self, top_list: List[Dict] = None):
        """Pretty-print top N rows."""
        if top_list is None:
            top_list = self.get_top_volume()
        
        n = CONFIG["print_top_n"]
        print(f"\n=== MEXC TOP {n} by 24h USD Volume (of top {len(top_list)}) ===")
        print(f"{'Rank':<4} {'Symbol':<12} {'Volume (USD)':<18} {'24h %':<8} {'Last Price':<12}")
        print("-" * 70)
        for item in top_list[:n]:
            print(f"{item['rank']:<4} {item['symbol']:<12} "
                  f"${item['quote_volume_usd']:,.0f} "
                  f"{item['price_change_percent']:>+7.2f}% "
                  f"${item['last_price']:<12}")

    def save_to_json(self, top_list: List[Dict] = None, filename: str = None):
        """Save the list to JSON."""
        if top_list is None:
            top_list = self.get_top_volume()
        if filename is None:
            filename = CONFIG["json_filename"]
        
        with open(filename, "w") as f:
            json.dump(top_list, f, indent=2)
        print(f"✅ Saved {len(top_list)} pairs to {filename}")


# ====================== EXAMPLE USAGE ======================
if __name__ == "__main__":
    # Uses whatever you set in CONFIG["default_limit"] (currently 200)
    fetcher = MEXCVolumeFetcher()            # ← no limit= here anymore
    top_pairs = fetcher.get_top_volume()
    
    fetcher.print_top_preview(top_pairs)
    fetcher.save_to_json(top_pairs)
