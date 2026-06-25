import os
import json
import requests
from datetime import datetime, timedelta
from config import (
    BULLISH_CALL_RISE_PCT, BULLISH_PUT_FALL_PCT,
    BULLISH_OTM_CALL_RISE_PCT, BULLISH_OTM_PUT_FALL_PCT,
    BEARISH_PUT_RISE_PCT, BEARISH_CALL_FALL_PCT,
    BEARISH_OTM_PUT_RISE_PCT, BEARISH_OTM_CALL_FALL_PCT,
    ALERT_COOLDOWN_MINUTES  # <-- imported from config
)

CACHE_FILE = 'iv_state.json'
MAX_HISTORY = 5

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
    if symbol == "NIFTY":
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
    print(f"🔍 ENTERED check_directional_signal for {symbol} at spot {spot_price}")

    if symbol not in ["NIFTY", "BANKNIFTY"]:
        print(f"⚠️ Symbol {symbol} not supported, returning.")
        return

    atm_strike = get_atm_strike(df, spot_price, symbol)
    print(f"🎯 ATM strike used: {atm_strike}")

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

    above_strikes, below_strikes = get_otm_strikes(df, atm_strike, step=100, count=2)
    otm_ce_ivs = [df.loc[df['strike'] == s, 'ce_iv'].values[0] for s in above_strikes]
    otm_pe_ivs = [df.loc[df['strike'] == s, 'pe_iv'].values[0] for s in above_strikes]
    otm_call_avg = sum(otm_ce_ivs)/len(otm_ce_ivs) if otm_ce_ivs else 0
    otm_put_avg = sum(otm_pe_ivs)/len(otm_pe_ivs) if otm_pe_ivs else 0
    below_ce_ivs = [df.loc[df['strike'] == s, 'ce_iv'].values[0] for s in below_strikes]
    below_pe_ivs = [df.loc[df['strike'] == s, 'pe_iv'].values[0] for s in below_strikes]
    otm_below_call_avg = sum(below_ce_ivs)/len(below_ce_ivs) if below_ce_ivs else 0
    otm_below_put_avg = sum(below_pe_ivs)/len(below_pe_ivs) if below_pe_ivs else 0

    current_snapshot = {
        'timestamp': datetime.now().isoformat(),
        'expiry': expiry,
        'spot': spot_price,
        'atm_strike': atm_strike,
        'atm_ce_iv': round(atm_ce_iv, 2),
        'atm_pe_iv': round(atm_pe_iv, 2),
        'otm_call_avg': round(otm_call_avg, 2),
        'otm_put_avg': round(otm_put_avg, 2),
        'otm_below_call_avg': round(otm_below_call_avg, 2),
        'otm_below_put_avg': round(otm_below_put_avg, 2),
        'ce_iv_by_strike': ce_iv_by_strike,
        'pe_iv_by_strike': pe_iv_by_strike,
        'ce_oi_by_strike': ce_oi_by_strike,
        'pe_oi_by_strike': pe_oi_by_strike,
        'ce_delta_by_strike': ce_delta_by_strike,
        'pe_delta_by_strike': pe_delta_by_strike,
        'ce_gamma_by_strike': ce_gamma_by_strike,
        'pe_gamma_by_strike': pe_gamma_by_strike,
        'ce_theta_by_strike': ce_theta_by_strike,
        'pe_theta_by_strike': pe_theta_by_strike,
        'ce_vega_by_strike': ce_vega_by_strike,
        'pe_vega_by_strike': pe_vega_by_strike,
    }

    state = load_state(symbol)
    history = state.get('history', [])
    last_alert_time = state.get('last_alert_time', None)

    print(f"📊 History length for {symbol}: {len(history)}")
    if history:
        print(f"   Last expiry in history: {history[-1].get('expiry')}, current expiry: {expiry}")

    if history and history[-1].get('expiry') != expiry:
        print(f"📅 Expiry changed from {history[-1].get('expiry')} to {expiry}. Clearing history.")
        history = []

    history.append(current_snapshot)
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    save_state(symbol, {'history': history, 'last_alert_time': last_alert_time})

    if len(history) < 2:
        print("✅ Initial state saved. Need one more snapshot for comparison.")
        return

    if last_alert_time:
        last_alert_dt = datetime.fromisoformat(last_alert_time)
        if (datetime.now() - last_alert_dt) < timedelta(minutes=ALERT_COOLDOWN_MINUTES):
            print(f"⏳ Cooldown active for {symbol} – last alert at {last_alert_dt.strftime('%H:%M')}")
            return
    print("⏳ Cooldown not active, proceeding to timeframe loop.")

    timeframes = {'5-min': -2, '10-min': -3, '15-min': -4}
    bullish_timeframes = []
    bearish_timeframes = []
    bullish_details = {}
    bearish_details = {}

    print("\n🔍 DEBUG – Percentage changes for SAME strike across time (fallback to nearest if missing):")
    for label, idx in timeframes.items():
        print(f"  Checking {label} (idx={idx})")
        if len(history) < abs(idx) + 1:
            print(f"    Not enough history (need {abs(idx)+1}, have {len(history)})")
            continue

        prev_snapshot = history[idx]
        curr_snapshot = history[-1]

        if ('ce_iv_by_strike' not in prev_snapshot or 'ce_iv_by_strike' not in curr_snapshot):
            print(f"    Snapshot format mismatch – skipping.")
            continue

        prev_strike = get_closest_strike(prev_snapshot['ce_iv_by_strike'], atm_strike, 100)
        curr_strike = get_closest_strike(curr_snapshot['ce_iv_by_strike'], atm_strike, 100)

        if prev_strike is None or curr_strike is None:
            print(f"    No strike within 100 points of {atm_strike} in history/current – skipping")
            continue

        curr_ce_iv = curr_snapshot['ce_iv_by_strike'].get(curr_strike)
        prev_ce_iv = prev_snapshot['ce_iv_by_strike'].get(prev_strike)
        curr_pe_iv = curr_snapshot['pe_iv_by_strike'].get(curr_strike)
        prev_pe_iv = prev_snapshot['pe_iv_by_strike'].get(prev_strike)

        if curr_ce_iv is None or prev_ce_iv is None or curr_pe_iv is None or prev_pe_iv is None:
            print(f"    IV data missing for found strikes – skipping")
            continue

        curr_otm_call_avg = curr_snapshot['otm_call_avg']
        prev_otm_call_avg = prev_snapshot['otm_call_avg']
        curr_otm_below_put_avg = curr_snapshot['otm_below_put_avg']
        prev_otm_below_put_avg = prev_snapshot['otm_below_put_avg']

        pct_delta_atm_ce = calculate_percentage_change(curr_ce_iv, prev_ce_iv)
        pct_delta_atm_pe = calculate_percentage_change(curr_pe_iv, prev_pe_iv)
        pct_delta_otm_call = calculate_percentage_change(curr_otm_call_avg, prev_otm_call_avg)
        pct_delta_otm_below_put = calculate_percentage_change(curr_otm_below_put_avg, prev_otm_below_put_avg)

        print(f"    {label}: ATM CE {pct_delta_atm_ce:+.2f}% | ATM PE {pct_delta_atm_pe:+.2f}% | "
              f"OTM Call {pct_delta_otm_call:+.2f}% | OTM Put {pct_delta_otm_below_put:+.2f}%")

        is_bullish = (
            pct_delta_atm_ce > BULLISH_CALL_RISE_PCT and
            pct_delta_atm_pe < BULLISH_PUT_FALL_PCT and
            pct_delta_otm_call > BULLISH_OTM_CALL_RISE_PCT and
            pct_delta_otm_below_put < BULLISH_OTM_PUT_FALL_PCT
        )
        if is_bullish:
            bullish_timeframes.append(label)
            bullish_details[label] = {
                'atm_ce_iv': (prev_ce_iv, curr_ce_iv, pct_delta_atm_ce),
                'atm_pe_iv': (prev_pe_iv, curr_pe_iv, pct_delta_atm_pe),
                'otm_call_avg': (prev_otm_call_avg, curr_otm_call_avg, pct_delta_otm_call),
                'otm_below_put_avg': (prev_otm_below_put_avg, curr_otm_below_put_avg, pct_delta_otm_below_put),
            }

        is_bearish = (
            pct_delta_atm_pe > BEARISH_PUT_RISE_PCT and
            pct_delta_atm_ce < BEARISH_CALL_FALL_PCT and
            pct_delta_otm_below_put > BEARISH_OTM_PUT_RISE_PCT and
            pct_delta_otm_call < BEARISH_OTM_CALL_FALL_PCT
        )
        if is_bearish:
            bearish_timeframes.append(label)
            bearish_details[label] = {
                'atm_pe_iv': (prev_pe_iv, curr_pe_iv, pct_delta_atm_pe),
                'atm_ce_iv': (prev_ce_iv, curr_ce_iv, pct_delta_atm_ce),
                'otm_below_put_avg': (prev_otm_below_put_avg, curr_otm_below_put_avg, pct_delta_otm_below_put),
                'otm_call_avg': (prev_otm_call_avg, curr_otm_call_avg, pct_delta_otm_call),
            }

    print(f"\n📊 Summary: Bullish timeframes = {bullish_timeframes}, Bearish timeframes = {bearish_timeframes}")

    if bullish_timeframes or bearish_timeframes:
        prev_snapshot = history[-2]
        if 'ce_iv_by_strike' in prev_snapshot:
            call_score, put_score, interp = calculate_smart_money_score(df, atm_strike, prev_snapshot)
        else:
            call_score, put_score, interp = 0, 0, "⚪ Smart Money data unavailable (cache rebuilding)"

        if bullish_timeframes and not bearish_timeframes:
            msg = f"🟢 *BULLISH Signal* ({symbol} Spot: {spot_price:.2f})\n\n"
            msg += f"✅ Triggered at: {', '.join(bullish_timeframes)}\n"
            non_bullish = [t for t in timeframes.keys() if t not in bullish_timeframes]
            if non_bullish:
                msg += f"⏳ Not confirmed at: {', '.join(non_bullish)}\n\n"
            msg += "*% Changes (same strike, fallback to nearest if needed):*\n"
            for label in bullish_timeframes:
                d = bullish_details[label]
                msg += f"  *{label}*: ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} ({d['atm_ce_iv'][2]:+.1f}%) | "
                msg += f"ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} ({d['atm_pe_iv'][2]:+.1f}%)\n"
                msg += f"    OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} ({d['otm_call_avg'][2]:+.1f}%) | "
                msg += f"OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} ({d['otm_below_put_avg'][2]:+.1f}%)\n"

        elif bearish_timeframes and not bullish_timeframes:
            msg = f"🔴 *BEARISH Signal* ({symbol} Spot: {spot_price:.2f})\n\n"
            msg += f"✅ Triggered at: {', '.join(bearish_timeframes)}\n"
            non_bearish = [t for t in timeframes.keys() if t not in bearish_timeframes]
            if non_bearish:
                msg += f"⏳ Not confirmed at: {', '.join(non_bearish)}\n\n"
            msg += "*% Changes (same strike, fallback to nearest if needed):*\n"
            for label in bearish_timeframes:
                d = bearish_details[label]
                msg += f"  *{label}*: ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} ({d['atm_pe_iv'][2]:+.1f}%) | "
                msg += f"ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} ({d['atm_ce_iv'][2]:+.1f}%)\n"
                msg += f"    OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} ({d['otm_below_put_avg'][2]:+.1f}%) | "
                msg += f"OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} ({d['otm_call_avg'][2]:+.1f}%)\n"

        else:
            msg = f"⚠️ *MIXED TIMEFRAME SIGNAL* ({symbol} Spot: {spot_price:.2f})\n\n"
            msg += f"🟢 Bullish at: {', '.join(bullish_timeframes)}\n"
            msg += f"🔴 Bearish at: {', '.join(bearish_timeframes)}\n\n"
            msg += "*Changes (same strike, fallback to nearest if needed):*\n"
            for label in bullish_timeframes:
                d = bullish_details[label]
                msg += f"  🟢 {label} - ATM Call Δ{d['atm_ce_iv'][2]:+.1f}% | ATM Put Δ{d['atm_pe_iv'][2]:+.1f}%\n"
            for label in bearish_timeframes:
                d = bearish_details[label]
                msg += f"  🔴 {label} - ATM Put Δ{d['atm_pe_iv'][2]:+.1f}% | ATM Call Δ{d['atm_ce_iv'][2]:+.1f}%\n"

        msg += f"\n🧠 *Smart Money Context:*\n"
        msg += f"   Call Score: {call_score}/6  {'🟢' if call_score >= 4 else '⚪'}\n"
        msg += f"   Put Score:  {put_score}/6  {'🔴' if put_score >= 4 else '⚪'}\n"
        msg += f"   → {interp}"

        send_telegram(msg)
        state['last_alert_time'] = datetime.now().isoformat()
        save_state(symbol, state)
    else:
        print("✅ No directional signal triggered at any timeframe.")