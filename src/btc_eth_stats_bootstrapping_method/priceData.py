import requests
import csv
import os
import pandas as pd
from loadCSV import load_from_file as _load
from saveCSV import save_to_file as _save
from datetime import datetime, timedelta, timezone


def download_new_file(fileName: str, cryptoSymbol: str) -> bool:
    existingDF = _load(fileName, ['date', f'{cryptoSymbol.lower()}_closing_price_usd'])

    if existingDF.empty:
        print('no existing data.. downloading new data..')
        return True

    latest_str = existingDF.iloc[-1]['date']
    latest_date = datetime.strptime(latest_str, '%Y-%m-%d').date()
    print(f'latest entry date: {latest_date}')

    now_utc = datetime.now(timezone.utc)
    current_date_utc = now_utc.date()
    print(f'current utc date: {current_date_utc}')
    print(f'current utc time: {now_utc.strftime("%H:%M:%S")} UTC')

    target_hour_utc = 13  # corresponds to 22:00 KST

    if now_utc.hour >= target_hour_utc:
        expected_latest_date = current_date_utc
    else:
        expected_latest_date = current_date_utc - timedelta(days=1)

    print(f'expected latest date (≥ {target_hour_utc}:00 UTC): {expected_latest_date}')

    if latest_date < expected_latest_date:
        print('data is behind.. downloading new data..')
        return True
    else:
        print('data is up to date.. no need to download..')
        return False


def download_crypto_daily_closing(crypto_symbol: str, fiat_symbol: str = 'usd', years: int = 2) -> None:
    print('')
    print(f' --- checking data on {crypto_symbol} --- ')

    fileName = f'{crypto_symbol.lower()}_daily_closing.csv'

    if not download_new_file(fileName, crypto_symbol):
        # skip download if existing data is good
        return
    
    url = 'https://min-api.cryptocompare.com/data/v2/histohour'
    
    # Fetch all hourly data needed (~2+ years)
    hourly_data = []
    cutoff_days = years * 365 + 30
    cutoff_time = int((datetime.now(timezone.utc) - timedelta(days=cutoff_days)).timestamp())

    to_ts = None
    while True:
        params = {
            'fsym': crypto_symbol.upper(),
            'tsym': fiat_symbol.upper(),
            'limit': 2000,
            'aggregate': 1
        }
        if to_ts is not None:
            params['toTs'] = to_ts

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f'request failed: {e}')
   
        if data['Response'] != 'Success':
            raise Exception(f'API error: {data.get('Message', 'Unknown error')}')
        
        batch = data['Data']['Data']
        if not batch:
            break

        hourly_data.extend(batch)

        if len(batch) < 2000:
            break

        oldest_time = batch[0]['time']  # oldest in this batch
        to_ts = oldest_time - 1

        if oldest_time < cutoff_time:
            break

    if not hourly_data:
        raise Exception('no data returned from the API')

    # sort just in case
    hourly_data.sort(key=lambda x: x['time'])

    # Filter to recent data
    recent_data = [entry for entry in hourly_data if entry['time'] >= cutoff_time]

    # Select only the 13:00 UTC hour (22:00 KST) and use its open price ≈ price at 22:00 KST
    target_hour = 13
    selected_data = []
    for entry in recent_data:
        entry_dt = datetime.fromtimestamp(entry['time'], tz=timezone.utc)
        if entry_dt.hour == target_hour:
            selected_data.append(entry)

    if not selected_data:
        raise Exception('no selected data after filtering')

    # latest entry (for printing)
    latest_entry = selected_data[-1]
    latest_date = datetime.fromtimestamp(latest_entry['time']).strftime('%Y-%m-%d')
    latest_price = latest_entry['open']  # open of the 13:00 UTC hour

    print('')
    print(f'latest closing price: ${latest_price:,.2f} on {latest_date} (~22:00 KST)')
    print(f'fetched {len(hourly_data)} total hourly points')
    print(f'selected {len(selected_data)} daily points (22:00 KST) for the last ~{years} years')

    # convert to DataFrame and save to file
    rows = []
    for entry in selected_data:
        date_str = datetime.fromtimestamp(entry['time']).strftime('%Y-%m-%d')
        price = entry['open']
        rows.append({'date': date_str, f'{crypto_symbol.lower()}_closing_price_usd': price})

    df = pd.DataFrame(rows)

    _save(df, fileName)


if __name__ == '__main__':
    download_crypto_daily_closing('btc')
