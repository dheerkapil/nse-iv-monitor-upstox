import os
import json
import requests
from datetime import datetime, timedelta
from config import (
    BULLISH_CALL_RISE_PCT, BULLISH_PUT_FALL_PCT,
    BULLISH_OTM_CALL_RISE_PCT, BULLISH_OTM_PUT_FALL_PCT,
    BEARISH_PUT_RISE_PCT, BEARISH_CALL_FALL_PCT,
    BEARISH_OTM_PUT_RISE_PCT, BEARISH_OTM_CALL_FALL_PCT
)

CACHE_FILE = 'iv_state.json'
MAX_HISTORY = 5
ALERT_COOLDOWN_MINUTES = 30   # Will move to config later

def send_telegram(message):
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    if not bot_token or not chat_id:
        print("⚠️ Telegram credentials missing, skipping alert.")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        r = requests.post(url, json={'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}, timeout=5)
        if r.status_code != 200:
            print(f"❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def load_state(symbol):
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
            return data.get(symbol, {})
    except (json.JSONDecodeError, ValueError):
        return {}

def save_state(symbol, state):
    data = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            data = {}
    data[symbol] = state
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_atm_strike(df, spot_price, symbol):
    """
    Find ATM strike.
    For NIFTY, round spot to nearest 100 to avoid 50-point strikes.
    For BANKNIFTY, use closest strike to actual spot.
    """
    if symbol == "NIFTY":
        # Round spot to nearest 100
        rounded_spot = round(spot_price / 100) * 100
        df['strike_diff'] = abs(df['strike'] - rounded_spot)
    else:
        df['strike_diff'] = abs(df['strike'] - spot_price)
    return df.loc[df['strike_diff'].idxmin(), 'strike']

def get_otm_strikes(df, atm_strike, step=100, count=2):
    available_strikes = sorted(df['strike'].unique())
    above = []
    below = []
    for i in range(1, count+1):
        target_up = atm_strike + i*step
        up_candidate = min(available_strikes, key=lambda x: abs(x - target_up))
        above.append(up_candidate)
        target_down = atm_strike - i*step
        down_candidate = min(available_strikes, key=lambda x: abs(x - target_down))
        below.append(down_candidate)
    return above, below

def calculate_percentage_change(current, previous):
    if previous == 0:
        return 0.0
    return ((current - previous) / previous) * 100

def get_closest_strike(strike_dict, target_strike, max_diff=100):
    if not strike_dict:
        return None
    keys = list(strike_dict.keys())
    closest_key = min(keys, key=lambda k: abs(float(k) - target_strike))
    if abs(float(closest_key) - target_strike) <= max_diff:
        return closest_key
    return None

def calculate_smart_money_score(df, atm_strike, prev_data):
    row = df[df['strike'] == atm_strike].iloc[0]
    prev_ce_oi = prev_data.get('ce_oi_by_strike', {}).get(atm_strike, row['ce_oi'])
    prev_pe_oi = prev_data.get('pe_oi_by_strike', {}).get(atm_strike, row['pe_oi'])
    prev_ce_iv = prev_data.get('ce_iv_by_strike', {}).get(atm_strike, row['ce_iv'])
    prev_pe_iv = prev_data.get('pe_iv_by_strike', {}).get(atm_strike, row['pe_iv'])
    prev_ce_delta = prev_data.get('ce_delta_by_strike', {}).get(atm_strike, row['ce_delta'])
    prev_pe_delta = prev_data.get('pe_delta_by_strike', {}).get(atm_strike, row['pe_delta'])
    prev_ce_gamma = prev_data.get('ce_gamma_by_strike', {}).get(atm_strike, row['ce_gamma'])
    prev_pe_gamma = prev_data.get('pe_gamma_by_strike', {}).get(atm_strike, row['pe_gamma'])
    prev_ce_theta = prev_data.get('ce_theta_by_strike', {}).get(atm_strike, row['ce_theta'])
    prev_pe_theta = prev_data.get('pe_theta_by_strike', {}).get(atm_strike, row['pe_theta'])
    prev_ce_vega = prev_data.get('ce_vega_by_strike', {}).get(atm_strike, row['ce_vega'])
    prev_pe_vega = prev_data.get('pe_vega_by_strike', {}).get(atm_strike, row['pe_vega'])

    call_score = 0
    if row['ce_oi'] > prev_ce_oi: call_score += 1
    if row['ce_iv'] > prev_ce_iv: call_score += 1
    if row['ce_delta'] > prev_ce_delta: call_score += 1
    if row['ce_gamma'] > prev_ce_gamma: call_score += 1
    if row['ce_theta'] < prev_ce_theta: call_score += 1
    if row['ce_vega'] < prev_ce_vega: call_score += 1

    put_score = 0
    if row['pe_oi'] > prev_pe_oi: put_score += 1
    if row['pe_iv'] > prev_pe_iv: put_score += 1
    if row['pe_delta'] < prev_pe_delta: put_score += 1
    if row['pe_gamma'] > prev_pe_gamma: put_score += 1
    if row['pe_theta'] < prev_pe_theta: put_score += 1
    if row['pe_vega'] < prev_pe_vega: put_score += 1

    if call_score >= 4 and put_score <= 2:
        interp = "🟢 STRONG BULLISH (Smart money buying calls)"
    elif put_score >= 4 and call_score <= 2:
        interp = "🔴 STRONG BEARISH (Smart money buying puts)"
    elif call_score >= 4 and put_score >= 4:
        interp = "🟡 HEDGING (Smart money hedging both sides)"
    else:
        interp = "⚪ LOW CONVICTION (No clear smart money direction)"
    return call_score, put_score, interp

def check_directional_signal(df, spot_price, symbol, expiry):
    if symbol not in ["NIFTY", "BANKNIFTY"]:
        return

    # Use the updated get_atm_strike with symbol
    atm_strike = get_atm_strike(df, spot_price, symbol)

    # Build per-strike dictionaries
    ce_iv_by_strike = {}
    pe_iv_by_strike = {}
    ce_oi_by_strike = {}
    pe_oi_by_strike = {}
    ce_delta_by_strike = {}
    pe_delta_by_strike = {}
    ce_gamma_by_strike = {}
    pe_gamma_by_strike = {}
    ce_theta_by_strike = {}
    pe_theta_by_strike = {}
    ce_vega_by_strike = {}
    pe_vega_by_strike = {}

    for _, row in df.iterrows():
        strike = row['strike']
        ce_iv_by_strike[strike] = row['ce_iv']
        pe_iv_by_strike[strike] = row['pe_iv']
        ce_oi_by_strike[strike] = row['ce_oi']
        pe_oi_by_strike[strike] = row['pe_oi']
        ce_delta_by_strike[strike] = row['ce_delta']
        pe_delta_by_strike[strike] = row['pe_delta']
        ce_gamma_by_strike[strike] = row['ce_gamma']
        pe_gamma_by_strike[strike] = row['pe_gamma']
        ce_theta_by_strike[strike] = row['ce_theta']
        pe_theta_by_strike[strike] = row['pe_theta']
        ce_vega_by_strike[strike] = row['ce_vega']
        pe_vega_by_strike[strike] = row['pe_vega']

    atm_ce_iv = df.loc[df['strike'] == atm_strike, 'ce_iv'].values[0]
    atm_pe_iv = df.loc[df['strike'] == atm_strike, 'pe_iv'].values[0]

    # OTM averages for message
    above_strikes, below_strikes = get_otm_strikes(df, atm_strike, step=100, count=2)
    otm_ce_ivs = [df.loc[df['strike'] == s, 'ce_iv'].values[0] for s in above_strikes]
    otm_pe_ivs = [df.loc[df['strike'] == s, 'pe_iv'].values[0] for s in above_strikes]
    otm_call_avg = sum(otm_ce_ivs)/len(otm_ce_ivs) if otm_ce_ivs else 0
    otm_put_avg = sum(otm_pe_ivs)/len(otm_pe_ivs) if otm_pe_ivs else 0
    below_ce_ivs = [df.loc[df['strike'] == s, 'ce_iv'].values[0] for s in below_strikes]
    below_pe_ivs = [df.loc[df['strike'] == s, 'pe_iv'].values[0] for s in below_strikes]
    otm_below_call_avg = sum(below_ce_ivs)/len(below_ce_ivs) if below_ce_ivs else 0
    otm_below_put_avg = sum(below_pe_ivs)/len(below_pe_ivs) if below_pe_ivs else 0

    # ... rest of the function (same as before, unchanged) ...