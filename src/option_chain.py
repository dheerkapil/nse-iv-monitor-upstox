import requests
import pandas as pd
from datetime import datetime, timedelta
import calendar
from config import UPSTOX_API_BASE, HEADERS

# ----- Static Holiday List (2026-2027) -----
def get_holidays():
    """Return set of NSE trading holidays (YYYY-MM-DD)."""
    return {
        # 2026
        "2026-01-26", "2026-03-03", "2026-04-03", "2026-04-14",
        "2026-05-28", "2026-08-15", "2026-10-02", "2026-12-25",
        # 2027
        "2027-01-26", "2027-03-22", "2027-04-02", "2027-04-14",
        "2027-10-02", "2027-12-25",
    }

def is_trading_day(date_str):
    """Check if date is a weekday and not a holiday."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    if date_obj.weekday() >= 5:  # Saturday or Sunday
        return False
    return date_str not in get_holidays()

def adjust_to_previous_trading_day(date_str, max_attempts=10):
    """Move backwards until a trading day is found."""
    current = datetime.strptime(date_str, "%Y-%m-%d")
    for _ in range(max_attempts):
        check = current.strftime("%Y-%m-%d")
        if is_trading_day(check):
            return check
        current -= timedelta(days=1)
    # Fallback: return original (should not happen)
    return date_str

def get_next_tuesday_expiry():
    """Return today if Tuesday and trading day, else next Tuesday."""
    today = datetime.today()
    # If today is Tuesday (weekday=1) and trading day, use today
    if today.weekday() == 1 and is_trading_day(today.strftime("%Y-%m-%d")):
        return today.strftime("%Y-%m-%d")
    # Otherwise find next Tuesday
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return adjust_to_previous_trading_day(next_tue.strftime("%Y-%m-%d"))

def get_last_tuesday_of_month(year, month):
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    days_back = (last_date.weekday() - 1) % 7
    return last_date - timedelta(days=days_back)

def get_expiry_date(symbol):
    """
    Return expiry date (YYYY-MM-DD) with holiday adjustment.
    - NIFTY: today if Tuesday else next Tuesday (weekly)
    - BANKNIFTY: last Tuesday of current month (monthly)
    """
    today = datetime.today()
    
    if symbol == "NIFTY":
        return get_next_tuesday_expiry()
    
    elif symbol == "BANKNIFTY":
        year = today.year
        month = today.month
        last_tue = get_last_tuesday_of_month(year, month)
        # If last_tue is before today, move to next month
        if last_tue.date() < today.date():
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            last_tue = get_last_tuesday_of_month(year, month)
        expiry = last_tue.strftime("%Y-%m-%d")
        return adjust_to_previous_trading_day(expiry)
    
    else:
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