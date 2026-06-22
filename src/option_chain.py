import requests
import pandas as pd
from datetime import datetime, timedelta
import calendar
from config import UPSTOX_API_BASE, HEADERS
from src.nse_holidays import get_adjusted_expiry  # <-- Import holiday handler

def get_next_tuesday_expiry():
    """Return next Tuesday for NIFTY (weekly)."""
    today = datetime.today()
    days_ahead = (1 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_tue = today + timedelta(days=days_ahead)
    return get_adjusted_expiry(next_tue.strftime("%Y-%m-%d"))  # <-- Adjust for holidays

def get_last_tuesday_of_month(year, month):
    """Return the last Tuesday of a given month."""
    last_day = calendar.monthrange(year, month)[1]
    last_date = datetime(year, month, last_day)
    days_back = (last_date.weekday() - 1) % 7
    last_tuesday = last_date - timedelta(days=days_back)
    return last_tuesday

def get_expiry_date(symbol):
    """
    Return expiry date (YYYY-MM-DD) based on instrument:
    - NIFTY: next Tuesday (weekly) with holiday adjustment
    - BANKNIFTY: last Tuesday of current month (monthly) with holiday adjustment
    """
    today = datetime.today()
    
    if symbol == "NIFTY":
        return get_next_tuesday_expiry()
    
    elif symbol == "BANKNIFTY":
        year = today.year
        month = today.month
        last_tue = get_last_tuesday_of_month(year, month)
        # If last_tue is before today, move to next month
        if last_tue.date() < today.date():
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1
            last_tue = get_last_tuesday_of_month(year, month)
        expiry = last_tue.strftime("%Y-%m-%d")
        return get_adjusted_expiry(expiry)  # <-- Adjust for holidays
    
    else:
        return get_next_tuesday_expiry()

# ... rest of fetch_option_chain function (unchanged)