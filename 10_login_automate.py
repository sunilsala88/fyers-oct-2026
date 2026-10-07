"""
Fyers API v3 - automated daily login (TOTP based)

Flow:
  1. send_login_otp_v2   -> request_key
  2. verify_otp (TOTP)   -> request_key
  3. verify_pin_v2 (PIN) -> temporary login token
  4. api/v3/token        -> auth_code (instead of the browser redirect to your redirect_uri)
  5. validate-authcode   -> access_token (via fyers_apiv3 SessionModel)

Setup:
  pip install fyers-apiv3 pyotp requests python-dotenv
  Enable "External 2FA TOTP" in myaccount.fyers.in and save the TOTP secret key.
  Fill in the .env file next to this script.
"""

import base64
import json
import os
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pyotp
import requests

from fyers_apiv3 import fyersModel



FY_ID =''                # your Fyers login id, e.g. XA12345
PIN = ''                # 4-digit PIN
TOTP_KEY = ''      # TOTP secret from Fyers 2FA setup
CLIENT_ID =  'G80JG7X1EA-200'     # e.g. G80JG7X1EA-200
SECRET_KEY = 'nYcduuLB3Tskaf7n'  # app secret from the API dashboard
REDIRECT_URI = 'https://fessorpro.com/'

TOKEN_FILE = Path(__file__).with_name("fyers_token.json")
VAGATOR = "https://api-t2.fyers.in/vagator/v2"
API_V3 = "https://api-t1.fyers.in/api/v3"


def b64(value: str) -> str:
    return base64.b64encode(str(value).encode()).decode()


def _post(session: requests.Session, url: str, payload: dict, **kw) -> dict:
    r = session.post(url, json=payload, timeout=15, **kw)
    try:
        data = r.json()
    except ValueError:
        raise RuntimeError(f"{url} -> HTTP {r.status_code}: {r.text[:300]}")
    if r.status_code not in (200, 308) or data.get("s") == "error":
        raise RuntimeError(f"{url} failed: {data}")
    return data


def get_auth_code() -> str:
    s = requests.Session()

    # 1. Start login
    d = _post(s, f"{VAGATOR}/send_login_otp_v2", {"fy_id": b64(FY_ID), "app_id": "2"})
    request_key = d["request_key"]

    # 2. TOTP
    d = _post(s, f"{VAGATOR}/verify_otp",
              {"request_key": request_key, "otp": pyotp.TOTP(TOTP_KEY).now()})
    request_key = d["request_key"]

    # 3. PIN
    d = _post(s, f"{VAGATOR}/verify_pin_v2",
              {"request_key": request_key, "identity_type": "pin", "identifier": b64(PIN)})
    login_token = d["data"]["access_token"]

    # 4. Authorise the app -> auth_code (same thing your generate-authcode URL gives you)
    app_id, app_type = CLIENT_ID.rsplit("-", 1)
    d = _post(
        s, f"{API_V3}/token",
        {
            "fyers_id": FY_ID,
            "app_id": app_id,
            "redirect_uri": REDIRECT_URI,
            "appType": app_type,
            "code_challenge": "",
            "state": "sample_state",
            "scope": "",
            "nonce": "",
            "response_type": "code",
            "create_cookie": True,
        },
        headers={"Authorization": f"Bearer {login_token}"},
    )
    url = d.get("Url") or d.get("data", {}).get("url", "")
    auth_code = parse_qs(urlparse(url).query).get("auth_code", [None])[0]
    if not auth_code:
        raise RuntimeError(f"auth_code not found in response: {d}")
    return auth_code


def generate_access_token() -> str:
    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
    )
    session.set_token(get_auth_code())
    resp = session.generate_token()
    if "access_token" not in resp:
        raise RuntimeError(f"Token generation failed: {resp}")
    return resp["access_token"]


def get_access_token(force: bool = False) -> str:
    """Return today's token, logging in only if no valid cached token exists."""
    if not force and TOKEN_FILE.exists():
        cached = json.loads(TOKEN_FILE.read_text())
        if cached.get("date") == date.today().isoformat():
            return cached["access_token"]

    token = generate_access_token()
    TOKEN_FILE.write_text(json.dumps({"date": date.today().isoformat(), "access_token": token}))
    return token


def get_fyers(force: bool = False) -> fyersModel.FyersModel:
    return fyersModel.FyersModel(client_id=CLIENT_ID, token=get_access_token(force),
                                 is_async=False, log_path="")


if __name__ == "__main__":
    fyers = get_fyers()
    print(fyers.get_profile())