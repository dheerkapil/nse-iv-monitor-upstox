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

# ========== ALERT THRESHOLDS (adjust as needed) ==========
# Bullish signals
BULLISH_CALL_RISE = 0.5      # ATM Call IV must increase by more than this (percentage points)
BULLISH_PUT_FALL = -0.5      # ATM Put IV must decrease by more than this (negative value)
BULLISH_OTM_CALL_RISE = 0.5  # OTM Call average IV must increase by more than this
BULLISH_OTM_PUT_FALL = -0.5  # OTM Put average IV must decrease by more than this (below ATM)

# Bearish signals
BEARISH_PUT_RISE = 0.5       # ATM Put IV must increase by more than this
BEARISH_CALL_FALL = -0.5     # ATM Call IV must decrease by more than this (negative)
BEARISH_OTM_PUT_RISE = 0.5   # OTM Put average IV must increase by more than this (below ATM)
BEARISH_OTM_CALL_FALL = -0.5 # OTM Call average IV must decrease by more than this (above ATM)
