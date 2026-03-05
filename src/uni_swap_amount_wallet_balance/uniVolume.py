import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


# Pool details
pool_address = "0x8c7080564b5a792a33ef2fd473fba6364d5495e5".lower()
network = "base"
timeframe = "day"  # Daily candles

# API endpoint
url = f"https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}/ohlcv/{timeframe}"

params = {
    "limit": 90,       # ~3 months of daily data
    "currency": "usd"
}

response = requests.get(url, params=params)

if response.status_code != 200:
    print("Error fetching data:", response.status_code, response.text)
else:
    data = response.json()
    ohlcv_list = data["data"]["attributes"]["ohlcv_list"]
    
    # Create DataFrame: [timestamp, open, high, low, close, volume_usd]
    df = pd.DataFrame(ohlcv_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # Convert timestamp to datetime (UTC)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Human-readable date string
    df['date_str'] = df['datetime'].dt.strftime('%Y-%m-%d')
    
    # Round volume for display
    df['volume'] = df['volume'].round(2)
    
    # Print daily table
    print("Daily Transaction Volume (USD) for cbBTC/WETH Pool on Base (Last ~3 Months)")
    print("-" * 60)
    print(f"{'Date':<12} {'Volume (USD)':>20}")
    print("-" * 60)
    for _, row in df.iterrows():
        print(f"{row['date_str']:<12} ${row['volume']:>19,.2f}")
    print("-" * 60)
    
    # Summary
    total_volume = df['volume'].sum()
    print(f"\nTotal volume over period: ${total_volume:,.2f}")
    print(f"Data points: {len(df)} days (~3 months or available history)")
    print(f"Date range: {df['date_str'].iloc[0]} to {df['date_str'].iloc[-1]}")
    
    # Save to CSV
    df[['datetime', 'open', 'high', 'low', 'close', 'volume']].to_csv('cbbtc_weth_3months_daily_volume.csv', index=False)
    print("\nDaily data saved to 'cbbtc_weth_3months_daily_volume.csv'")
    
    # Plot: Line chart
    plt.figure(figsize=(14, 7))
    plt.plot(df['datetime'], df['volume'], linewidth=2, color='darkblue')
    plt.fill_between(df['datetime'], df['volume'], alpha=0.2, color='blue')
    plt.title('Daily Transaction Volume (USD) – cbBTC/WETH Pool on Base (Last ~3 Months)', fontsize=14)
    plt.xlabel('Date (UTC)', fontsize=12)
    plt.ylabel('Daily Volume (USD)', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    # Format x-axis for shorter period (show weeks + months)
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_minor_locator(mdates.DayLocator(interval=7))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.show()
