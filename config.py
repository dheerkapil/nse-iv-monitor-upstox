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

TRACK_INDICES = ["NIFTY"]  # Only NIFTY for now

# ========== ALERT THRESHOLDS (Percentage-Based) ==========
# Bullish signals (percentage change relative to previous value)
BULLISH_CALL_RISE_PCT = 1.0      # ATM Call IV must increase by more than 5%
BULLISH_PUT_FALL_PCT = - 0.5     # ATM Put IV must decrease by more than 3%
BULLISH_OTM_CALL_RISE_PCT = 1.0  # OTM Call average IV must increase by more than 5%
BULLISH_OTM_PUT_FALL_PCT = -0.5  # OTM Put average IV must decrease by more than 3%

# Bearish signals
BEARISH_PUT_RISE_PCT = 1.0       # ATM Put IV must increase by more than 5%
BEARISH_CALL_FALL_PCT = -0.5     # ATM Call IV must decrease by more than 3%
BEARISH_OTM_PUT_RISE_PCT = 1.0   # OTM Put average IV must increase by more than 5%
BEARISH_OTM_CALL_FALL_PCT = -0.5 # OTM Call average IV must decrease by more than 3%