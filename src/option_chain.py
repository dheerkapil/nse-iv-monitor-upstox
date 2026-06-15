import requests
import pandas as pd
from datetime import datetime, timedelta
from config import UPSTOX_API_BASE, HEADERS

def get_next_tuesday_expiry():
    """
    Returns the next Tuesday's date as YYYY-MM-DD.
    Nifty weekly expiry is Tuesday.
    """
    today = datetime.today()
    # weekday: Monday=0, Tuesday=1, ..., Sunday=6
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return next_tue.strftime("%Y-%m-%d")

def fetch_spot_price(instrument_key):
    """
    Fetch live spot price from Upstox market quote LTP endpoint.
    Returns float or None if failed.
    """
    url = f"{UPSTOX_API_BASE}/market/quote/ltp"
    params = {"instrument_key": instrument_key}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # Extract LTP from response (structure may vary)
            ltp = data.get('data', {}).get(instrument_key, {}).get('ltp')
            if ltp:
                return float(ltp)
            # Alternative structure
            if data.get('data') and isinstance(data['data'], list):
                for item in data['data']:
                    if item.get('instrument_key') == instrument_key:
                        return float(item.get('ltp', 0))
        print(f"⚠️ Could not fetch spot price. Status: {response.status_code}")
        return None
    except Exception as e:
        print(f"⚠️ Exception fetching spot price: {e}")
        return None

def fetch_option_chain(instrument_key, expiry_date=None):
    """
    Fetch option chain for a given instrument and expiry.
    Returns: (DataFrame, spot_price) or (None, None) on failure.
    """
    if expiry_date is None:
        expiry_date = get_next_tuesday_expiry()

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

        # If spot price is N/A, fetch it from LTP endpoint
        if spot_price == 'N/A' or spot_price is None:
            print("⚠️ underlying_spot is N/A, fetching from LTP endpoint...")
            fetched_spot = fetch_spot_price(instrument_key)
            if fetched_spot:
                spot_price = fetched_spot
                print(f"✅ Fetched spot price from LTP: ₹{spot_price}")
            else:
                print("⚠️ Could not fetch spot price. Signals will be skipped.")

        for strike_data in data['data']:
            ce = strike_data.get('ce') or {}
            pe = strike_data.get('pe') or {}
            row = {
                'strike': strike_data['strike_price'],
                'spot_price': spot_price,
                'ce_ltp': ce.get('ltp', 0),
                'ce_iv': ce.get('iv', 0),
                'ce_delta': ce.get('delta', 0),
                'ce_gamma': ce.get('gamma', 0),
                'ce_theta': ce.get('theta', 0),
                'ce_vega': ce.get('vega', 0),
                'ce_oi': ce.get('oi', 0),
                'ce_volume': ce.get('volume', 0),
                'ce_change_oi': ce.get('change_oi', 0),
                'pe_ltp': pe.get('ltp', 0),
                'pe_iv': pe.get('iv', 0),
                'pe_delta': pe.get('delta', 0),
                'pe_gamma': pe.get('gamma', 0),
                'pe_theta': pe.get('theta', 0),
                'pe_vega': pe.get('vega', 0),
                'pe_oi': pe.get('oi', 0),
                'pe_volume': pe.get('volume', 0),
                'pe_change_oi': pe.get('change_oi', 0),
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        # Add IV skew (call IV - put IV)
        df['iv_skew'] = df['ce_iv'] - df['pe_iv']

        print(f"✅ Fetched {len(df)} strikes, Spot: ₹{spot_price}")
        return df, spot_price

    except Exception as e:
        print(f"❌ Exception in fetch_option_chain: {e}")
        return None, None