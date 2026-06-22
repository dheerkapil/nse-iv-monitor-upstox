#!/usr/bin/env python3
import pytz
import re
from datetime import datetime
from src.option_chain import fetch_option_chain, get_expiry_date
from src.utils import save_to_csv
from src.alerts import check_directional_signal
from config import TRACK_INDICES, INSTRUMENTS

def clean_spot_price(spot):
    if spot is None:
        return None
    cleaned = re.sub(r'[^\d.\-]', '', str(spot).strip())
    try:
        return float(cleaned)
    except ValueError:
        return None

def main():
    print("=" * 60)
    print("🚀 Upstox Option Chain Fetcher - Multi-Timeframe Signals")
    print(f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 60)

    for symbol in TRACK_INDICES:
        print(f"\n📊 Processing {symbol}...")
        instrument_key = INSTRUMENTS.get(symbol)
        if not instrument_key:
            print(f"❌ Unknown symbol: {symbol}")
            continue

        expiry = get_expiry_date(symbol)
        df, spot = fetch_option_chain(instrument_key, expiry)

        if df is not None and not df.empty:
            save_to_csv(df, symbol, expiry)

            spot_num = clean_spot_price(spot)
            if spot_num is not None:
                print(f"✅ Cleaned spot price: {spot_num}")
                check_directional_signal(df, spot_num, symbol)
            else:
                print(f"⚠️ Could not parse spot price: '{spot}'")

            print(f"✅ Data saved for {symbol}")
        else:
            print(f"❌ Failed to fetch data for {symbol}")

    print("\n" + "=" * 60)
    print("✅ Done processing all symbols.")
    print("=" * 60)

if __name__ == "__main__":
    main()