import os
import json
import requests
from datetime import datetime
from config import (
    BULLISH_CALL_RISE, BULLISH_PUT_FALL, BULLISH_OTM_CALL_RISE, BULLISH_OTM_PUT_FALL,
    BEARISH_PUT_RISE, BEARISH_CALL_FALL, BEARISH_OTM_PUT_RISE, BEARISH_OTM_CALL_FALL
)

CACHE_FILE = 'iv_state.json'
MAX_HISTORY = 4  # Current + 3 previous snapshots (5-min, 10-min, 15-min)

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
    """Load full state for a symbol (includes history)."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
            return data.get(symbol, {})
    except (json.JSONDecodeError, ValueError):
        return {}

def save_state(symbol, state):
    """Save full state for a symbol (preserves history for other symbols)."""
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

def get_atm_strike(df, spot_price):
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

def check_directional_signal(df, spot_price, symbol):
    if symbol != "NIFTY":
        return

    # Calculate current IV snapshot
    atm_strike = get_atm_strike(df, spot_price)
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
        'spot': spot_price,
        'atm_strike': atm_strike,
        'atm_ce_iv': round(atm_ce_iv, 2),
        'atm_pe_iv': round(atm_pe_iv, 2),
        'otm_call_avg': round(otm_call_avg, 2),
        'otm_put_avg': round(otm_put_avg, 2),
        'otm_below_call_avg': round(otm_below_call_avg, 2),
        'otm_below_put_avg': round(otm_below_put_avg, 2),
    }

    # Load existing state for this symbol
    state = load_state(symbol)
    history = state.get('history', [])

    # Add current snapshot to history
    history.append(current_snapshot)
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]  # Keep only last 4

    # Save updated state
    save_state(symbol, {'history': history})

    # Need at least 2 snapshots to compare (current + one previous)
    if len(history) < 2:
        print("✅ Initial state saved. Need one more snapshot for comparison.")
        return

    # Check bullish and bearish conditions for each timeframe
    # Timeframe indices: -1 = current (now), -2 = 5 min ago, -3 = 10 min ago, -4 = 15 min ago
    timeframes = {
        '5-min': -2,
        '10-min': -3,
        '15-min': -4
    }

    bullish_timeframes = []
    bearish_timeframes = []
    bullish_details = {}
    bearish_details = {}

    for label, idx in timeframes.items():
        if len(history) < abs(idx) + 1:  # Not enough history for this timeframe
            continue

        prev = history[idx]
        curr = history[-1]

        # Calculate changes
        delta_atm_ce = curr['atm_ce_iv'] - prev['atm_ce_iv']
        delta_atm_pe = curr['atm_pe_iv'] - prev['atm_pe_iv']
        delta_otm_call = curr['otm_call_avg'] - prev['otm_call_avg']
        delta_otm_below_put = curr['otm_below_put_avg'] - prev['otm_below_put_avg']

        # Check bullish condition
        is_bullish = (
            delta_atm_ce > BULLISH_CALL_RISE and
            delta_atm_pe < BULLISH_PUT_FALL and
            delta_otm_call > BULLISH_OTM_CALL_RISE and
            delta_otm_below_put < BULLISH_OTM_PUT_FALL
        )
        if is_bullish:
            bullish_timeframes.append(label)
            bullish_details[label] = {
                'atm_ce_iv': (prev['atm_ce_iv'], curr['atm_ce_iv'], delta_atm_ce),
                'atm_pe_iv': (prev['atm_pe_iv'], curr['atm_pe_iv'], delta_atm_pe),
                'otm_call_avg': (prev['otm_call_avg'], curr['otm_call_avg'], delta_otm_call),
                'otm_below_put_avg': (prev['otm_below_put_avg'], curr['otm_below_put_avg'], delta_otm_below_put),
            }

        # Check bearish condition
        is_bearish = (
            delta_atm_pe > BEARISH_PUT_RISE and
            delta_atm_ce < BEARISH_CALL_FALL and
            delta_otm_below_put > BEARISH_OTM_PUT_RISE and
            delta_otm_call < BEARISH_OTM_CALL_FALL
        )
        if is_bearish:
            bearish_timeframes.append(label)
            bearish_details[label] = {
                'atm_pe_iv': (prev['atm_pe_iv'], curr['atm_pe_iv'], delta_atm_pe),
                'atm_ce_iv': (prev['atm_ce_iv'], curr['atm_ce_iv'], delta_atm_ce),
                'otm_below_put_avg': (prev['otm_below_put_avg'], curr['otm_below_put_avg'], delta_otm_below_put),
                'otm_call_avg': (prev['otm_call_avg'], curr['otm_call_avg'], delta_otm_call),
            }

    # Build and send alert
    if bullish_timeframes and bearish_timeframes:
        # Mixed signal
        msg = f"⚠️ *MIXED SIGNAL* ({symbol} Spot: {spot_price:.2f})\n\n"
        msg += f"🟢 Bullish at: {', '.join(bullish_timeframes)}\n"
        msg += f"🔴 Bearish at: {', '.join(bearish_timeframes)}\n\n"
        msg += "🟢 *Bullish Details:*\n"
        for label in bullish_timeframes:
            d = bullish_details[label]
            msg += f"  *{label}*: ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} (Δ{d['atm_ce_iv'][2]:+.2f}) | "
            msg += f"ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} (Δ{d['atm_pe_iv'][2]:+.2f})\n"
            msg += f"    OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} (Δ{d['otm_call_avg'][2]:+.2f}) | "
            msg += f"OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} (Δ{d['otm_below_put_avg'][2]:+.2f})\n"
        msg += "\n🔴 *Bearish Details:*\n"
        for label in bearish_timeframes:
            d = bearish_details[label]
            msg += f"  *{label}*: ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} (Δ{d['atm_pe_iv'][2]:+.2f}) | "
            msg += f"ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} (Δ{d['atm_ce_iv'][2]:+.2f})\n"
            msg += f"    OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} (Δ{d['otm_below_put_avg'][2]:+.2f}) | "
            msg += f"OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} (Δ{d['otm_call_avg'][2]:+.2f})\n"
        send_telegram(msg)

    elif bullish_timeframes:
        # Pure bullish
        msg = f"🟢 *BULLISH Signal* ({symbol} Spot: {spot_price:.2f})\n\n"
        msg += f"✅ Triggered at: {', '.join(bullish_timeframes)}\n"
        non_bullish = [t for t in timeframes.keys() if t not in bullish_timeframes]
        if non_bullish:
            msg += f"⏳ Not confirmed at: {', '.join(non_bullish)}\n\n"
        msg += "*Changes:*\n"
        for label in bullish_timeframes:
            d = bullish_details[label]
            msg += f"  *{label}*: ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} (Δ{d['atm_ce_iv'][2]:+.2f}) | "
            msg += f"ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} (Δ{d['atm_pe_iv'][2]:+.2f})\n"
            msg += f"    OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} (Δ{d['otm_call_avg'][2]:+.2f}) | "
            msg += f"OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} (Δ{d['otm_below_put_avg'][2]:+.2f})\n"
        send_telegram(msg)

    elif bearish_timeframes:
        # Pure bearish
        msg = f"🔴 *BEARISH Signal* ({symbol} Spot: {spot_price:.2f})\n\n"
        msg += f"✅ Triggered at: {', '.join(bearish_timeframes)}\n"
        non_bearish = [t for t in timeframes.keys() if t not in bearish_timeframes]
        if non_bearish:
            msg += f"⏳ Not confirmed at: {', '.join(non_bearish)}\n\n"
        msg += "*Changes:*\n"
        for label in bearish_timeframes:
            d = bearish_details[label]
            msg += f"  *{label}*: ATM Put {d['atm_pe_iv'][0]:.2f}→{d['atm_pe_iv'][1]:.2f} (Δ{d['atm_pe_iv'][2]:+.2f}) | "
            msg += f"ATM Call {d['atm_ce_iv'][0]:.2f}→{d['atm_ce_iv'][1]:.2f} (Δ{d['atm_ce_iv'][2]:+.2f})\n"
            msg += f"    OTM Put {d['otm_below_put_avg'][0]:.2f}→{d['otm_below_put_avg'][1]:.2f} (Δ{d['otm_below_put_avg'][2]:+.2f}) | "
            msg += f"OTM Call {d['otm_call_avg'][0]:.2f}→{d['otm_call_avg'][1]:.2f} (Δ{d['otm_call_avg'][2]:+.2f})\n"
        send_telegram(msg)

    else:
        print("✅ No directional signal triggered at any timeframe.")