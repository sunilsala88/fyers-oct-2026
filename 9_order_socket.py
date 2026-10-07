from fyers_apiv3.FyersWebsocket import order_ws


CLIENT_ID = 'G80JG7X1EA-200'

with open('access_token.txt') as f:
    access_token = f.read().strip()


def on_order(message):
    print('Order update:', message, flush=True)


def on_trade(message):
    print('Trade update:', message, flush=True)


def on_position(message):
    print('Position update:', message, flush=True)


def on_general(message):
    print('General update:', message, flush=True)


def on_error(message):
    print('Error:', message, flush=True)


def on_close(message):
    print('Connection closed:', message, flush=True)


def on_open():
    # Any combination of: OnOrders, OnTrades, OnPositions, OnGeneral
    fyers_socket.subscribe(data_type='OnOrders,OnTrades,OnPositions,OnGeneral')
    fyers_socket.keep_running()


fyers_socket = order_ws.FyersOrderSocket(
    access_token=f'{CLIENT_ID}:{access_token}',   # socket needs "client_id:access_token"
    log_path='',
    write_to_file=False,
    reconnect=True,
    on_connect=on_open,
    on_close=on_close,
    on_error=on_error,
    on_orders=on_order,
    on_trades=on_trade,
    on_positions=on_position,
    on_general=on_general,
)

fyers_socket.connect()

# Stop the stream with:
# fyers_socket.close_connection()
