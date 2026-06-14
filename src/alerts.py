import requests
import json
import os
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
STATE_FILE = 'iv_state.json'

def send_telegram(message):
    """Send message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing, skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code != 200:
            print(f"❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram send failed: {e}")

def load_previous_iv():
    """Load stored IVs from JSON file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_current_iv(iv_data):
    """Save current IVs to JSON file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(iv_data, f, indent=2)

def check_iv_alerts(df, spot_price, iv_threshold_atm=2.0, iv_threshold_otm=5.0):
    """
    Compares current IVs with previous values and sends alerts.
    df: DataFrame with strikes, ce_iv, pe_iv, etc.
    spot_price: current underlying price.
    iv_threshold_atm: absolute % change to trigger alert for ATM.
    iv_threshold_otm: absolute % change for OTM strikes.
    """
    # Find ATM strike
    df['strike_diff'] = abs(df['strike'] - spot_price)
    atm_strike = df.loc[df['strike_diff'].idxmin(), 'strike']
    atm_ce_iv = df.loc[df['strike'] == atm_strike, 'ce_iv'].values[0]
    atm_pe_iv = df.loc[df['strike'] == atm_strike, 'pe_iv'].values[0]

    # Pick OTM strikes: e.g., 200 points above and below ATM
    otm_up_strike = atm_strike + 200
    otm_down_strike = atm_strike - 200
    # Find closest available strikes
    otm_up = df.iloc[(df['strike'] - otm_up_strike).abs().argsort()[:1]]['strike'].values[0]
    otm_down = df.iloc[(df['strike'] - otm_down_strike).abs().argsort()[:1]]['strike'].values[0]
    otm_up_ce_iv = df.loc[df['strike'] == otm_up, 'ce_iv'].values[0]
    otm_up_pe_iv = df.loc[df['strike'] == otm_up, 'pe_iv'].values[0]
    otm_down_ce_iv = df.loc[df['strike'] == otm_down, 'ce_iv'].values[0]
    otm_down_pe_iv = df.loc[df['strike'] == otm_down, 'pe_iv'].values[0]

    # Build current IV snapshot
    current = {
        "timestamp": datetime.now().isoformat(),
        "spot": spot_price,
        "atm_strike": atm_strike,
        "atm_ce_iv": round(atm_ce_iv, 2),
        "atm_pe_iv": round(atm_pe_iv, 2),
        "otm_up_strike": otm_up,
        "otm_up_ce_iv": round(otm_up_ce_iv, 2),
        "otm_up_pe_iv": round(otm_up_pe_iv, 2),
        "otm_down_strike": otm_down,
        "otm_down_ce_iv": round(otm_down_ce_iv, 2),
        "otm_down_pe_iv": round(otm_down_pe_iv, 2),
    }

    previous = load_previous_iv()
    alerts = []

    if previous:
        # ATM alerts
        if abs(current['atm_ce_iv'] - previous.get('atm_ce_iv', 0)) >= iv_threshold_atm:
            alerts.append(f"ATM Call IV changed: {previous.get('atm_ce_iv')}% → {current['atm_ce_iv']}%")
        if abs(current['atm_pe_iv'] - previous.get('atm_pe_iv', 0)) >= iv_threshold_atm:
            alerts.append(f"ATM Put IV changed: {previous.get('atm_pe_iv')}% → {current['atm_pe_iv']}%")

        # OTM alerts (using the same threshold for both sides)
        for side, key in [('OTM Up Call', 'otm_up_ce_iv'), ('OTM Up Put', 'otm_up_pe_iv'),
                          ('OTM Down Call', 'otm_down_ce_iv'), ('OTM Down Put', 'otm_down_pe_iv')]:
            if abs(current[key] - previous.get(key, 0)) >= iv_threshold_otm:
                alerts.append(f"{side} IV changed: {previous.get(key)}% → {current[key]}%")

    if alerts:
        message = f"*IV Alert – NIFTY (Spot: {spot_price})*\n" + "\n".join(alerts)
        send_telegram(message)
    else:
        print("✅ No IV alerts triggered.")

    # Save current state for next comparison
    save_current_iv(current)
