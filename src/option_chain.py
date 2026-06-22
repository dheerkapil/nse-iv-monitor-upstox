import requests
import pandas as pd
from datetime import datetime, timedelta
import calendar
from config import UPSTOX_API_BASE, HEADERS
from src.nse_holidays import get_adjusted_expiry

def get_next_tuesday_expiry():
    """Return next Tuesday for NIFTY (weekly)."""
    today = datetime.today()
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return get_adjusted_expiry(next_tue.strftime("%Y-%m-%d"))

def get_last_tuesday_of_month(year, month):
    """Return the last Tuesday of a given month."""
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    days_back = (last_date.weekday() - 1) % 7
    last_tuesday = last_date - timedelta(days=days_back)
    return last_tuesday

def get_expiry_date(symbol):
    """
    Return expiry date (YYYY-MM-DD) based on instrument:
    - NIFTY: next Tuesday (weekly) with holiday adjustment
    - BANKNIFTY: last Tuesday of current month (monthly) with holiday adjustment
    """
    today = datetime.today()
    
    if symbol == "NIFTY":
        return get_next_tuesday_expiry()
    
    elif symbol == "BANKNIFTY":
        year = today.year
        month = today.month
        last_tue = get_last_tuesday_of_month(year, month)
        if last_tue.date() < today.date():
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            last_tue = get_last_tuesday_of_month(year, month)
        expiry = last_tue.strftime("%Y-%m-%d")
        return get_adjusted_expiry(expiry)
    
    else:
        return get_next_tuesday_expiry()

def fetch_option_chain(instrument_key, expiry_date):
    """
    Fetch option chain for a given instrument and expiry date.
    Returns: (DataFrame, spot_price) or (None, None) on failure.
    """
    url = f"{UPSTOX_API_BASE}/option/chain"
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_date
    }

    print(f"📡 Fetching {instrument_key} exp {expiry_date}...")

    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)

        if response.status_code != 200:
            print(f"❌ API Error {response.status_code}: {response.text[:200]}")
            return None, None

        data = response.json()
        if not data.get('data'):
            print("❌ No data in response")
            return None, None

        rows = []
        spot_price = data.get('underlying_spot', 'N/A')
        if spot_price == 'N/A' and data['data']:
            spot_price = data['data'][0].get('underlying_spot_price', 'N/A')

        for strike_data in data['data']:
            call = strike_data.get('call_options') or {}
            put = strike_data.get('put_options') or {}

            call_market = call.get('market_data') or {}
            call_greeks = call.get('option_greeks') or {}

            put_market = put.get('market_data') or {}
            put_greeks = put.get('option_greeks') or {}

            row = {
                'strike': strike_data['strike_price'],
                'spot_price': spot_price,
                'ce_ltp': call_market.get('ltp', 0),
                'ce_iv': call_greeks.get('iv', 0),
                'ce_delta': call_greeks.get('delta', 0),
                'ce_gamma': call_greeks.get('gamma', 0),
                'ce_theta': call_greeks.get('theta', 0),
                'ce_vega': call_greeks.get('vega', 0),
                'ce_oi': call_market.get('oi', 0),
                'ce_volume': call_market.get('volume', 0),
                'pe_ltp': put_market.get('ltp', 0),
                'pe_iv': put_greeks.get('iv', 0),
                'pe_delta': put_greeks.get('delta', 0),
                'pe_gamma': put_greeks.get('gamma', 0),
                'pe_theta': put_greeks.get('theta', 0),
                'pe_vega': put_greeks.get('vega', 0),
                'pe_oi': put_market.get('oi', 0),
                'pe_volume': put_market.get('volume', 0),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        df['iv_skew'] = df['ce_iv'] - df['pe_iv']

        print(f"✅ Fetched {len(df)} strikes, Spot: ₹{spot_price}")
        return df, spot_price

    except Exception as e:
        print(f"❌ Exception in fetch_option_chain: {e}")
        return None, None