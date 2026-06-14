import os
import json
import requests
from datetime import datetime

CACHE_FILE = 'iv_state.json'

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

def load_previous_state():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_current_state(state):
    with open(CACHE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def get_atm_strike(df, spot_price):
    try:
        spot_price = float(spot_price)
    except (ValueError, TypeError):
        return None
    df['strike_diff'] = abs(df['strike'] - spot_price)
    return df.loc[df['strike_diff'].idxmin(), 'strike']

def get_otm_strikes(df, atm_strike, step=100, count=2):
    """Get 'count' strikes above and below atm_strike by step increments."""
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

def check_directional_signal(df, spot_price, symbol):
    if symbol != "NIFTY":
        return

    # Validate spot price
    try:
        spot_price = float(spot_price)
    except (ValueError, TypeError):
        print(f"⚠️ Invalid spot price: {spot_price}. Skipping alert.")
        return

    atm_strike = get_atm_strike(df, spot_price)
    if atm_strike is None:
        print("⚠️ Could not determine ATM strike.")
        return

    atm_ce_iv = df.loc[df['strike'] == atm_strike, 'ce_iv'].values[0]
    atm_pe_iv = df.loc[df['strike'] == atm_strike, 'pe_iv'].values[0]

    # OTM strikes: two above and two below (100, 200 points)
    above_strikes, below_strikes = get_otm_strikes(df, atm_strike, step=100, count=2)
    otm_ce_ivs = []
    otm_pe_ivs = []
    for s in above_strikes:
        otm_ce_ivs.append(df.loc[df['strike'] == s, 'ce_iv'].values[0])
        otm_pe_ivs.append(df.loc[df['strike'] == s, 'pe_iv'].values[0])
    otm_call_avg = sum(otm_ce_ivs)/len(otm_ce_ivs) if otm_ce_ivs else 0
    otm_put_avg = sum(otm_pe_ivs)/len(otm_pe_ivs) if otm_pe_ivs else 0

    # For puts OTM we use below strikes
    below_ce_ivs = []
    below_pe_ivs = []
    for s in below_strikes:
        below_ce_ivs.append(df.loc[df['strike'] == s, 'ce_iv'].values[0])
        below_pe_ivs.append(df.loc[df['strike'] == s, 'pe_iv'].values[0])
    otm_below_call_avg = sum(below_ce_ivs)/len(below_ce_ivs) if below_ce_ivs else 0
    otm_below_put_avg = sum(below_pe_ivs)/len(below_pe_ivs) if below_pe_ivs else 0

    current_state = {
        'timestamp': datetime.now().isoformat(),
        'spot': spot_price,
        'atm_strike': atm_strike,
        'atm_ce_iv': round(atm_ce_iv, 2),
        'atm_pe_iv': round(atm_pe_iv, 2),
        'otm_call_avg': round(otm_call_avg, 2),
        'otm_put_avg': round(otm_put_avg, 2),
        'otm_below_call_avg': round(otm_below_call_avg, 2),
        'otm_below_put_avg': round(otm_below_put_avg, 2),
    }

    prev = load_previous_state()
    if not prev:
        save_current_state(current_state)
        print("✅ Initial state saved. No comparison.")
        return

    # Compute changes
    delta_atm_ce = current_state['atm_ce_iv'] - prev.get('atm_ce_iv', 0)
    delta_atm_pe = current_state['atm_pe_iv'] - prev.get('atm_pe_iv', 0)
    delta_otm_call = current_state['otm_call_avg'] - prev.get('otm_call_avg', 0)
    delta_otm_put = current_state['otm_put_avg'] - prev.get('otm_put_avg', 0)
    delta_otm_below_call = current_state['otm_below_call_avg'] - prev.get('otm_below_call_avg', 0)
    delta_otm_below_put = current_state['otm_below_put_avg'] - prev.get('otm_below_put_avg', 0)

    bullish = False
    bearish = False
    alert_msg = ""

    # Bullish condition
    if (delta_atm_ce > 1.0 and delta_atm_pe < -0.5 and
        delta_otm_call > 1.0 and delta_otm_below_put < -0.5):
        bullish = True
        alert_msg = (
            f"🟢 *BULLISH Signal* (NIFTY Spot: {spot_price:.2f})\n"
            f"ATM Call IV: {prev['atm_ce_iv']} → {current_state['atm_ce_iv']} (Δ{delta_atm_ce:+.2f})\n"
            f"ATM Put IV: {prev['atm_pe_iv']} → {current_state['atm_pe_iv']} (Δ{delta_atm_pe:+.2f})\n"
            f"OTM Calls (above) Avg: {prev['otm_call_avg']} → {current_state['otm_call_avg']} (Δ{delta_otm_call:+.2f})\n"
            f"OTM Puts (below) Avg: {prev['otm_below_put_avg']} → {current_state['otm_below_put_avg']} (Δ{delta_otm_below_put:+.2f})"
        )

    # Bearish condition
    if (delta_atm_pe > 1.0 and delta_atm_ce < -0.5 and
        delta_otm_below_put > 1.0 and delta_otm_call < -0.5):
        bearish = True
        alert_msg = (
            f"🔴 *BEARISH Signal* (NIFTY Spot: {spot_price:.2f})\n"
            f"ATM Put IV: {prev['atm_pe_iv']} → {current_state['atm_pe_iv']} (Δ{delta_atm_pe:+.2f})\n"
            f"ATM Call IV: {prev['atm_ce_iv']} → {current_state['atm_ce_iv']} (Δ{delta_atm_ce:+.2f})\n"
            f"OTM Puts (below) Avg: {prev['otm_below_put_avg']} → {current_state['otm_below_put_avg']} (Δ{delta_otm_below_put:+.2f})\n"
            f"OTM Calls (above) Avg: {prev['otm_call_avg']} → {current_state['otm_call_avg']} (Δ{delta_otm_call:+.2f})"
        )

    if bullish or bearish:
        send_telegram(alert_msg)
    else:
        print("✅ No directional signal triggered.")

    save_current_state(current_state)
