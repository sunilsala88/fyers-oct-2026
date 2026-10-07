import io
import time
from collections import deque
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from fyers_apiv3 import fyersModel


CLIENT_ID = 'G80JG7X1EA-200'
RESOLUTION = '1'  # 1 minute
DAYS = 365
CHUNK_DAYS = 100  # Fyers allows at most 100 days per request for intraday resolutions
OUTPUT_DIR = Path('data/nifty50_1min')
COMBINED_FILE = Path('data/nifty50_1min_1y.parquet')

# Fyers API limits: 10 requests/second, 200 requests/minute, 100,000 requests/day.
# Stay comfortably below them.
MAX_PER_SECOND = 8
MAX_PER_MINUTE = 180
MAX_PER_DAY = 90_000
MAX_RETRIES = 5

NIFTY50_CSV_URL = 'https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv'

# Used only if the live list from NSE cannot be downloaded
FALLBACK_NIFTY50 = [
    'ADANIENT', 'ADANIPORTS', 'APOLLOHOSP', 'ASIANPAINT', 'AXISBANK', 'BAJAJ-AUTO', 'BAJAJFINSV',
    'BAJFINANCE', 'BEL', 'BHARTIARTL', 'CIPLA', 'COALINDIA', 'DRREDDY', 'EICHERMOT', 'ETERNAL',
    'GRASIM', 'HCLTECH', 'HDFCBANK', 'HDFCLIFE', 'HINDALCO', 'HINDUNILVR', 'ICICIBANK', 'INDIGO',
    'INFY', 'ITC', 'JIOFIN', 'JSWSTEEL', 'KOTAKBANK', 'LT', 'M&M', 'MARUTI', 'MAXHEALTH',
    'NESTLEIND', 'NTPC', 'ONGC', 'POWERGRID', 'RELIANCE', 'SBILIFE', 'SBIN', 'SHRIRAMFIN',
    'SUNPHARMA', 'TATACONSUM', 'TATASTEEL', 'TCS', 'TECHM', 'TITAN', 'TMPV', 'TRENT',
    'ULTRACEMCO', 'BSE',
]

# Token saved by first.py
with open('access_token.txt') as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=access_token, is_async=False, log_path='')


class RateLimiter:
    """Sliding-window limiter that blocks until a request is allowed under every window."""

    def __init__(self, limits):
        # limits: list of (max_requests, window_seconds)
        self.windows = [(max_req, secs, deque()) for max_req, secs in limits]

    def wait(self):
        while True:
            now = time.monotonic()
            sleep_for = 0
            for max_req, secs, calls in self.windows:
                while calls and now - calls[0] >= secs:
                    calls.popleft()
                if len(calls) >= max_req:
                    sleep_for = max(sleep_for, secs - (now - calls[0]))
            if sleep_for <= 0:
                break
            time.sleep(sleep_for + 0.01)
        now = time.monotonic()
        for _, _, calls in self.windows:
            calls.append(now)


limiter = RateLimiter([(MAX_PER_SECOND, 1), (MAX_PER_MINUTE, 60), (MAX_PER_DAY, 86_400)])


def get_nifty50_symbols():
    try:
        resp = requests.get(NIFTY50_CSV_URL, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        resp.raise_for_status()
        symbols = pd.read_csv(io.StringIO(resp.text))['Symbol'].str.strip().tolist()
        if len(symbols) >= 50:
            print(f'Loaded {len(symbols)} Nifty 50 symbols from NSE')
            return symbols
    except Exception as e:
        print(f'Could not download Nifty 50 list from NSE ({e}), using fallback list')
    return FALLBACK_NIFTY50


def is_rate_limited(response):
    return response.get('code') in (429, -429) or 'limit' in str(response.get('message', '')).lower()


def history_request(data):
    """Call the history API through the rate limiter, retrying on rate-limit and network errors."""
    for attempt in range(1, MAX_RETRIES + 1):
        limiter.wait()
        try:
            response = fyers.history(data=data)
        except Exception as e:
            response = {'s': 'error', 'message': str(e)}

        if response.get('s') in ('ok', 'no_data'):
            return response

        backoff = 2 ** attempt
        if is_rate_limited(response):
            backoff = max(backoff, 60)  # minute window exceeded, let it reset
        print(f'  attempt {attempt}/{MAX_RETRIES} failed: {response}; retrying in {backoff}s')
        time.sleep(backoff)
    raise RuntimeError(f'Giving up on {data["symbol"]} {data["range_from"]}..{data["range_to"]}: {response}')


def fetch_history(symbol, start, end):
    candles = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS - 1), end)
        response = history_request({
            'symbol': symbol,
            'resolution': RESOLUTION,
            'date_format': '1',  # dates as yyyy-mm-dd
            'range_from': chunk_start.strftime('%Y-%m-%d'),
            'range_to': chunk_end.strftime('%Y-%m-%d'),
            'cont_flag': '1',
        })
        candles.extend(response.get('candles', []))
        chunk_start = chunk_end + timedelta(days=1)

    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df = df.drop_duplicates('timestamp').sort_values('timestamp')
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
    df['volume'] = df['volume'].astype('int64')
    return df[['datetime', 'open', 'high', 'low', 'close', 'volume']].reset_index(drop=True)


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    end = date.today()
    start = end - timedelta(days=DAYS)
    symbols = get_nifty50_symbols()
    failed = []

    for i, name in enumerate(symbols, 1):
        path = OUTPUT_DIR / f'{name}.parquet'
        if path.exists():
            print(f'[{i}/{len(symbols)}] {name}: already downloaded, skipping')
            continue
        try:
            df = fetch_history(f'NSE:{name}-EQ', start, end)
        except RuntimeError as e:
            print(f'[{i}/{len(symbols)}] {name}: {e}')
            failed.append(name)
            continue
        df.to_parquet(path, index=False, compression='snappy')
        print(f'[{i}/{len(symbols)}] {name}: saved {len(df)} candles to {path}')

    # Combine all per-stock files into one Parquet file with a symbol column
    frames = [pd.read_parquet(OUTPUT_DIR / f'{name}.parquet').assign(symbol=name)
              for name in symbols if (OUTPUT_DIR / f'{name}.parquet').exists()]
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined['symbol'] = combined['symbol'].astype('category')
        combined.to_parquet(COMBINED_FILE, index=False, compression='snappy')
        print(f'\nSaved {len(combined)} rows for {len(frames)} stocks to {COMBINED_FILE}')

    if failed:
        print(f'Failed symbols (re-run the script to retry): {failed}')
