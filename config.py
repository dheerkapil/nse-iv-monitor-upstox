import os

# Upstox API Configuration
UPSTOX_ACCESS_TOKEN = os.getenv('UPSTOX_ACCESS_TOKEN')
UPSTOX_API_BASE = "https://api.upstox.com/v2"

HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {UPSTOX_ACCESS_TOKEN}"
}

# Indices to track
INSTRUMENTS = {
    "NIFTY": "NSE_INDEX|Nifty 50",
    "BANKNIFTY": "NSE_INDEX|Nifty Bank",
}

TRACK_INDICES = ["NIFTY", "BANKNIFTY"]

# ========== PER-SYMBOL ALERT THRESHOLDS (Percentage-Based) ==========
# NIFTY thresholds (as per your screenshot)
# BANKNIFTY thresholds are set higher to filter out noise due to higher volatility.
THRESHOLDS = {
    "NIFTY": {
        "BULLISH_CALL_RISE_PCT": 3.0,
        "BULLISH_PUT_FALL_PCT": -1.5,
        "BULLISH_OTM_CALL_RISE_PCT": 2.0,
        "BULLISH_OTM_PUT_FALL_PCT": -1.0,
        "BEARISH_PUT_RISE_PCT": 3.0,
        "BEARISH_CALL_FALL_PCT": -1.5,
        "BEARISH_OTM_PUT_RISE_PCT": 2.0,
        "BEARISH_OTM_CALL_FALL_PCT": -1.0,
    },
    "BANKNIFTY": {
        # Higher thresholds to reduce false signals in a more volatile index
        "BULLISH_CALL_RISE_PCT": 4.0,
        "BULLISH_PUT_FALL_PCT": -2.0,
        "BULLISH_OTM_CALL_RISE_PCT": 4.0,
        "BULLISH_OTM_PUT_FALL_PCT": -2.0,
        "BEARISH_PUT_RISE_PCT": 4.0,
        "BEARISH_CALL_FALL_PCT": -2.0,
        "BEARISH_OTM_PUT_RISE_PCT": 4.0,
        "BEARISH_OTM_CALL_FALL_PCT": -2.0,
    }
}

# ========== COOLDOWN SETTINGS ==========
ALERT_COOLDOWN_MINUTES = 2