import requests
import pandas as pd
from datetime import datetime, timedelta
import calendar
from config import UPSTOX_API_BASE, HEADERS, INSTRUMENTS

# ----- Expiry fetching from Upstox API -----
def get_available_expiries(instrument_key):
    """Fetch list of available expiry dates for an instrument from Upstox."""
    url = f"{UPSTOX_API_BASE}/option/expiry"
    params = {"instrument_key": instrument_key}
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            expiries = data.get('data', [])
            if expiries:
                return sorted(expiries)  # nearest first
            else:
                print(f"⚠️ No expiries returned for {instrument_key}")
        else:
            print(f"⚠️ Expiry API error {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"⚠️ Expiry API exception: {e}")
    return None

def get_next_tuesday_expiry():
    """Fallback: calculate next Tuesday (no holiday adjustment)."""
    today = datetime.today()
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return next_tue.strftime("%Y-%m-%d")

def get_expiry_date(symbol):
    """
    Return the nearest available expiry for the symbol.
    Uses Upstox expiry API, fallback to next Tuesday if fails.
    """
    instrument_key = INSTRUMENTS.get(symbol)
    if not instrument_key:
        return get_next_tuesday_expiry()
    
    expiries = get_available_expiries(instrument_key)
    if expiries:
        nearest = expiries[0]
        print(f"📅 Nearest expiry for {symbol}: {nearest}")
        return nearest
    else:
        print(f"⚠️ Falling back to Tuesday calculation for {symbol}")
        return get_next_tuesday_expiry()

# ----- Fetch option chain (unchanged) -----
def fetch_option_chain(instrument_key, expiry_date, retries=3, timeout=60):
    url = f"{UPSTOX_API_BASE}/option/chain"
    params = {
        "instrument_key": instrument_key,
        "expiry_date": expiry_date
    }

    print(f"📡 Fetching {instrument_key} exp {expiry_date}...")

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
            if response.status_code == 200:
                break
            else:
                print(f"⚠️ Attempt {attempt+1}: Status {response.status_code}")
                if attempt == retries:
                    print(f"❌ API Error {response.status_code}: {response.text[:200]}")
                    return None, None
        except requests.exceptions.Timeout:
            print(f"⏰ Attempt {attempt+1} timed out. Retrying...")
            if attempt == retries:
                print("❌ All retries failed due to timeout.")
                return None, None
        except Exception as e:
            print(f"❌ Exception: {e}")
            return None, None

    # Process response
    try:
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
        print(f"❌ Exception in processing: {e}")
        return None, None