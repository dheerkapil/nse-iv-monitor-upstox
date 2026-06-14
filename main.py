#!/usr/bin/env python3
from src.option_chain import fetch_option_chain, get_next_tuesday_expiry
from src.utils import save_to_csv, calculate_pcr, get_top_iv_strikes
from config import TRACK_INDICES, INSTRUMENTS
from datetime import datetime
import pytz

def main():
    print("=" * 60)
    print("🚀 Upstox Option Chain Fetcher")
    print(f"⏰ {datetime.now(pytz.timezone('Asia/Kolkata')).strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("=" * 60)
    success = 0
    for symbol in TRACK_INDICES:
        print(f"\n📊 Processing {symbol}...")
        instrument_key = INSTRUMENTS.get(symbol)
        if not instrument_key:
            print(f"❌ Unknown symbol: {symbol}")
            continue
        expiry = get_next_tuesday_expiry()
        df, spot = fetch_option_chain(instrument_key, expiry)
        if df is not None and not df.empty:
            pcr = calculate_pcr(df)
            if pcr:
                print(f"📈 PCR (OI): {pcr}")
            top_ce = get_top_iv_strikes(df, 3, 'ce')
            if not top_ce.empty:
                print("🔥 Top Call IVs:")
                for _, row in top_ce.iterrows():
                    print(f"   Strike {row['strike']}: {row['ce_iv']:.2f}%")
            top_pe = get_top_iv_strikes(df, 3, 'pe')
            if not top_pe.empty:
                print("🔥 Top Put IVs:")
                for _, row in top_pe.iterrows():
                    print(f"   Strike {row['strike']}: {row['pe_iv']:.2f}%")
            save_to_csv(df, symbol, expiry)
            success += 1
        else:
            print(f"❌ Failed to fetch data for {symbol}")
    print("\n" + "=" * 60)
    print(f"✅ Done. Success: {success}/{len(TRACK_INDICES)}")
    print("=" * 60)

if __name__ == "__main__":
    main()