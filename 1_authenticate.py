from urllib.parse import parse_qs, urlparse
import webbrowser

from fyers_apiv3 import fyersModel


CLIENT_ID = 'G80JG7X1EA-200'
SECRET_KEY = 'nYcduuLB3Tskaf7n'
REDIRECT_URI =  'https://fessorpro.com/'


session = fyersModel.SessionModel(
    client_id=CLIENT_ID,
    secret_key=SECRET_KEY,
    redirect_uri=REDIRECT_URI,
    response_type='code',
    grant_type='authorization_code',
    state='sample_state',
)

# Step 1: log in to Fyers in the browser
login_url = session.generate_authcode()
print('Login URL:', login_url)
webbrowser.open(login_url, new=1)

# Step 2: after login you are redirected to REDIRECT_URI; paste that full URL here
redirected_url = input('Paste the full redirected URL: ').strip()
auth_code = parse_qs(urlparse(redirected_url).query)['auth_code'][0]

# Step 3: exchange the auth code for an access token
session.set_token(auth_code)
response = session.generate_token()

if response.get('s') != 'ok':
    raise SystemExit(f'Failed to generate access token: {response}')

access_token = response['access_token']
print('Access token:', access_token)

with open('access_token.txt', 'w') as f:
    f.write(access_token)

# Quick check that the token works
fyers = fyersModel.FyersModel(client_id=CLIENT_ID, token=access_token, is_async=False, log_path='')
print(fyers.get_profile())
