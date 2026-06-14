#!/usr/bin/env python3
import pytz
from datetime import datetime
from src.option_chain import fetch_option_chain, get_next_tuesday_expiry
from src.utils import save_to_csv
from src.alerts import check_directional_signal

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
        check_directional_signal(df, spot, symbol)
        print(f"✅ Data saved and signals checked for {symbol}")
    else:
        print(f"❌ Failed to fetch data for {symbol}")

    print("=" * 60)

if __name__ == "__main__":
    main()
