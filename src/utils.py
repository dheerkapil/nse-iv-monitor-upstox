import pandas as pd
import os
from datetime import datetime

def save_to_csv(df, symbol, expiry_date):
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data/{symbol}_{expiry_date}_{timestamp}.csv"
    df.to_csv(filename, index=False)
    print(f"💾 Saved: {filename}")
    return filename

def calculate_pcr(df):
    total_ce = df['ce_oi'].sum()
    total_pe = df['pe_oi'].sum()
    if total_ce == 0:
        return None
    return round(total_pe / total_ce, 2)

def get_top_iv_strikes(df, n=3, option_type='ce'):
    col = f'{option_type}_iv'
    return df.nlargest(n, col)[['strike', col]]