from fyers_apiv3.FyersWebsocket import data_ws


CLIENT_ID = 'G80JG7X1EA-200'

with open('access_token.txt') as f:
    access_token = f.read().strip()

SYMBOLS = ['NSE:NIFTY50-INDEX', 'NSE:NIFTYBANK-INDEX']
latest = {}     # latest tick per symbol, updated on every message


def on_message(message):
    # Print the full raw message exactly as received from the socket
    print(message, flush=True)
    if 'symbol' in message:
        latest[message['symbol']] = message


def on_error(message):
    print('Error:', message)


def on_close(message):
    print('Connection closed:', message)


def on_open():
    fyers_socket.subscribe(symbols=SYMBOLS, data_type='SymbolUpdate')
    fyers_socket.keep_running()


fyers_socket = data_ws.FyersDataSocket(
    access_token=f'{CLIENT_ID}:{access_token}',   # socket needs "client_id:access_token"
    log_path='',
    litemode=False,                               # True = only LTP, False = full tick
    write_to_file=False,
    reconnect=True,
    on_connect=on_open,
    on_close=on_close,
    on_error=on_error,
    on_message=on_message,
)

fyers_socket.connect()

# Stop the stream with:
# fyers_socket.close_connection()
