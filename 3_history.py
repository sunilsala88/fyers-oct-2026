import csv
import time
from datetime import date, datetime, timedelta, timezone

from fyers_apiv3 import fyersModel


CLIENT_ID = 'G80JG7X1EA-200'
SYMBOL = 'NSE:RELIANCE-EQ'
RESOLUTION = '1'  # 1 minute
YEARS = 5
CHUNK_DAYS = 100  # Fyers allows at most 100 days per request for intraday resolutions
OUTPUT_FILE = 'reliance_1min_5y.csv'

IST = timezone(timedelta(hours=5, minutes=30))

# Token saved by first.py
with open('access_token.txt') as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=access_token, is_async=False, log_path='')


def fetch_history(symbol, resolution, start, end):
    candles = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
        data = {
            'symbol': symbol,
            'resolution': resolution,
            'date_format': '1',  # dates as yyyy-mm-dd
            'range_from': chunk_start.strftime('%Y-%m-%d'),
            'range_to': chunk_end.strftime('%Y-%m-%d'),
            'cont_flag': '1',
        }
        response = fyers.history(data=data)
        if response.get('s') == 'ok':
            candles.extend(response.get('candles', []))
            print(f'{chunk_start} to {chunk_end}: {len(response.get("candles", []))} candles')
        elif response.get('s') == 'no_data':
            print(f'{chunk_start} to {chunk_end}: no data')
        else:
            raise SystemExit(f'Failed to fetch {chunk_start} to {chunk_end}: {response}')

        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(0.2)  # stay under the API rate limit

    # Remove duplicates and sort by timestamp
    unique = {c[0]: c for c in candles}
    return [unique[ts] for ts in sorted(unique)]


def save_to_csv(candles, path):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['datetime', 'open', 'high', 'low', 'close', 'volume'])
        for ts, o, h, l, c, v in candles:
            dt = datetime.fromtimestamp(ts, tz=IST).strftime('%Y-%m-%d %H:%M:%S')
            writer.writerow([dt, o, h, l, c, v])


if __name__ == '__main__':
    end = date.today()
    start = end - timedelta(days=365 * YEARS)
    candles = fetch_history(SYMBOL, RESOLUTION, start, end)
    save_to_csv(candles, OUTPUT_FILE)
    print(f'\nSaved {len(candles)} candles to {OUTPUT_FILE}')
