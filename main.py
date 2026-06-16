#!/usr/bin/env python3
import pytz
import re
from datetime import datetime
from src.option_chain import fetch_option_chain, get_next_tuesday_expiry
from src.utils import save_to_csv
from src.alerts import check_directional_signal

def clean_spot_price(spot):
    """
    Remove all non-numeric characters except decimal point and minus sign.
    Handles: ₹23989.15, 23989.15\n, 23,989.15, etc.
    """
    if spot is None:
        return None
    # Convert to string and remove everything except digits, decimal point, and minus sign
    cleaned = re.sub(r'[^\d.\-]', '', str(spot).strip())
    try:
        return float(cleaned)
    except ValueError:
        return None

def main():
    print("=" * 60)
    print("🚀 Upstox Option Chain Fetcher - Directional Signals")
    print(f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 60)

    symbol = "NIFTY"
    instrument_key = "NSE_INDEX|Nifty 50"
    expiry = get_next_tuesday_expiry()

    df, spot = fetch_option_chain(instrument_key, expiry)

    if df is not None and not df.empty:
        save_to_csv(df, symbol, expiry)
        
        # Clean the spot price
        spot_num = clean_spot_price(spot)
        if spot_num is not None:
            print(f"✅ Cleaned spot price: {spot_num}")
            check_directional_signal(df, spot_num, symbol)
        else:
            print(f"⚠️ Could not parse spot price: '{spot}'")
        
        print(f"✅ Data saved for {symbol}")
    else:
        print(f"❌ Failed to fetch data for {symbol}")

    print("=" * 60)

if __name__ == "__main__":
    main()