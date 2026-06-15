import requests
import pandas as pd
from datetime import datetime, timedelta
from config import UPSTOX_API_BASE, HEADERS

def get_next_tuesday_expiry():
    today = datetime.today()
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return next_tue.strftime("%Y-%m-%d")

def calculate_spot_from_option_chain(df):
    """Calculate approximate spot price from option chain using ATM strike."""
    if df.empty:
        return None
    df['iv_diff'] = abs(df['ce_iv'] - df['pe_iv'])
    atm_idx = df['iv_diff'].idxmin()
    return float(df.loc[atm_idx, 'strike'])

def fetch_spot_price(instrument_key, option_chain_df=None):
    """Fetch spot price: try LTP endpoint, fallback to option chain calculation."""
    # Try LTP endpoint
    url = f"{UPSTOX_API_BASE}/market/quote/ltp"
    params = {"instrument_key": instrument_key}
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ltp = data.get('data', {}).get(instrument_key, {}).get('ltp')
            if ltp:
                print(f"✅ Fetched spot from LTP: ₹{ltp}")
                return float(ltp)
    except Exception as e:
        print(f"⚠️ LTP endpoint error: {e}")
    
    # Fallback: calculate from option chain
    if option_chain_df is not None:
        spot = calculate_spot_from_option_chain(option_chain_df)
        if spot:
            print(f"✅ Calculated spot from option chain: ₹{spot}")
            return spot
    
    print("⚠️ Could not determine spot price")
    return None

def fetch_option_chain(instrument_key, expiry_date=None):
    if expiry_date is None:
        expiry_date = get_next_tuesday_expiry()

    url = f"{UPSTOX_API_BASE}/option/chain"
    params = {"instrument_key": instrument_key, "expiry_date": expiry_date}

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

        for strike_data in data['data']:
            ce = strike_data.get('ce') or {}
            pe = strike_data.get('pe') or {}
            rows.append({
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
                'pe_ltp': pe.get('ltp', 0),
                'pe_iv': pe.get('iv', 0),
                'pe_delta': pe.get('delta', 0),
                'pe_gamma': pe.get('gamma', 0),
                'pe_theta': pe.get('theta', 0),
                'pe_vega': pe.get('vega', 0),
                'pe_oi': pe.get('oi', 0),
                'pe_volume': pe.get('volume', 0),
            })

        df = pd.DataFrame(rows)
        df['iv_skew'] = df['ce_iv'] - df['pe_iv']

        # If spot is N/A, calculate from option chain
        if spot_price == 'N/A' or spot_price is None:
            calculated_spot = fetch_spot_price(instrument_key, df)
            if calculated_spot:
                spot_price = calculated_spot
                df['spot_price'] = spot_price

        print(f"✅ Fetched {len(df)} strikes, Spot: ₹{spot_price}")
        return df, spot_price

    except Exception as e:
        print(f"❌ Exception: {e}")
        return None, None