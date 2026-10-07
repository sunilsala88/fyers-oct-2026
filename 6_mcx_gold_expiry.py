import pandas as pd
from fyers_apiv3 import fyersModel


CLIENT_ID = 'G80JG7X1EA-200'
MCX_MASTER_URL = 'https://public.fyers.in/sym_details/MCX_COM.csv'

with open('access_token.txt') as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=access_token, is_async=False, log_path='')


def get_futures_expiries(underlying='GOLD'):
    # Master file has no header: col 8 = expiry (epoch), col 9 = symbol ticker, col 13 = underlying
    master = pd.read_csv(MCX_MASTER_URL, header=None)
    fut = master[(master[13] == underlying) & master[9].str.endswith('FUT')]

    df = pd.DataFrame({
        'symbol': fut[9],
        'expiry': pd.to_datetime(fut[8], unit='s', utc=True).dt.tz_convert('Asia/Kolkata').dt.date,
    }).sort_values('expiry').reset_index(drop=True)
    return df


def get_option_expiries(fut_symbol):
    # Fyers option chain for MCX needs a futures symbol, e.g. MCX:GOLD26DECFUT
    response = fyers.optionchain(data={'symbol': fut_symbol, 'strikecount': 1, 'timestamp': ''})
    if response.get('s') != 'ok':
        raise SystemExit(f'Failed to fetch option chain: {response}')

    df = pd.DataFrame(response['data']['expiryData'])
    df['expiry'] = pd.to_datetime(df['date'], format='%d-%m-%Y').dt.date
    return df[['expiry', 'expiry_flag']]


if __name__ == '__main__':
    futures = get_futures_expiries('GOLD')
    print('===== GOLD Futures Expiries =====')
    print(futures.to_string(index=False))

    options = get_option_expiries(futures['symbol'].iloc[0])
    print('\n===== GOLD Options Expiries =====')
    print(options.to_string(index=False))

    futures.to_csv('gold_futures_expiry.csv', index=False)
    options.to_csv('gold_options_expiry.csv', index=False)
