import json
import csv
import os

# ==================== CONFIG ====================
json_filename = "gecko_global_trending_24h.json"   # ← change only if you use a different file
# ===============================================

# Load the JSON
with open(json_filename, 'r', encoding='utf-8') as f:
    data = json.load(f)

pools = data.get('pools', [])

# UPDATED COLUMN ORDER: pool_name first, then the two ranks, then the rest
headers = [
    'pool_name',
    'gecko_terminal_rank',   # ← now right after pool_name
    'coingecko_rank',        # ← immediately after GeckoTerminal rank
    'base_token_name',
    'base_token_symbol',
    'quote_token_name',
    'quote_token_symbol',
    'chain',
    'dex',
    'liquidity_usd',
    'coingecko_link'
]

# Prepare rows
rows = []
for pool in pools:
    attrs = pool.get('attributes', {})
    rels = pool.get('relationships', {})
    base = pool.get('base_token', {})
    quote = pool.get('quote_token', {})

    row = {
        'pool_name': attrs.get('name', ''),
        'gecko_terminal_rank': pool.get('gecko_terminal_rank', ''),
        'coingecko_rank': pool.get('coingecko_rank', ''),
        'base_token_name': base.get('name', ''),
        'base_token_symbol': base.get('symbol', ''),
        'quote_token_name': quote.get('name', ''),
        'quote_token_symbol': quote.get('symbol', ''),
        'chain': rels.get('network', {}).get('data', {}).get('id', ''),
        'dex': rels.get('dex', {}).get('data', {}).get('id', ''),
        'liquidity_usd': attrs.get('reserve_in_usd', ''),
        'coingecko_link': pool.get('coingecko_link', '')
    }
    rows.append(row)

# Write to CSV (same base name, .csv extension)
csv_filename = os.path.splitext(json_filename)[0] + '.csv'

with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ Successfully converted with updated column order!")
print(f"   Input  : {json_filename}")
print(f"   Output : {csv_filename}")
print(f"   Pools processed : {len(rows)}")
print(f"   Columns (in order): {', '.join(headers)}")
