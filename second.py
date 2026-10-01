from fyers_apiv3 import fyersModel


CLIENT_ID = 'G80JG7X1EA-200'

# Token saved by first.py
with open('access_token.txt') as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=access_token, is_async=False, log_path='')


def get_funds():
    response = fyers.funds()
    if response.get('s') != 'ok':
        raise SystemExit(f'Failed to fetch funds: {response}')

    print('===== Funds =====')
    for item in response['fund_limit']:
        print(f"{item['title']:<30} Equity: {item['equityAmount']:>14,.2f}   Commodity: {item['commodityAmount']:>14,.2f}")
    return response['fund_limit']


def get_positions():
    response = fyers.positions()
    if response.get('s') != 'ok':
        raise SystemExit(f'Failed to fetch positions: {response}')

    positions = response.get('netPositions', [])
    print('\n===== Positions =====')
    if not positions:
        print('No open positions')
    for pos in positions:
        print(f"{pos['symbol']:<30} Qty: {pos['netQty']:>6}   Avg: {pos['netAvg']:>10,.2f}   "
              f"LTP: {pos['ltp']:>10,.2f}   P&L: {pos['pl']:>10,.2f}   ({pos['productType']})")

    overall = response.get('overall', {})
    if overall:
        print(f"\nTotal P&L: {overall.get('pl_total', 0):,.2f}   "
              f"Realized: {overall.get('pl_realized', 0):,.2f}   "
              f"Unrealized: {overall.get('pl_unrealized', 0):,.2f}")
    return positions


if __name__ == '__main__':
    get_funds()
    get_positions()
