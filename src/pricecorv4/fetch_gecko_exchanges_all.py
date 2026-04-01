import requests
import json
from typing import List, Dict

def get_all_exchange_ids() -> List[str]:
    url = "https://api.coingecko.com/api/v3/exchanges/list"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error for bad status codes
        
        data: List[Dict] = response.json()
        
        # Extract just the IDs
        exchange_ids = [exchange["id"] for exchange in data]
        
        print(f"✅ Successfully fetched {len(exchange_ids)} exchange IDs")
        return exchange_ids
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API request failed: {e}")
        return []

# Usage
if __name__ == "__main__":
    ids = get_all_exchange_ids()
    
    # Example: print first 10
    print("First 10 exchange IDs:", ids[:10])
    
    # Save to JSON for later use
    with open("coingecko_exchange_ids.json", "w") as f:
        json.dump(ids, f, indent=2)
    print("💾 Saved to coingecko_exchange_ids.json")
