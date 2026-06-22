import requests
import json
from datetime import datetime, timedelta
from functools import lru_cache

@lru_cache(maxsize=1)
def fetch_nse_holidays():
    """
    Fetch NSE trading holidays from the official NSE API.
    Caches the result to avoid repeated API calls.
    Returns a set of date strings in YYYY-MM-DD format.
    """
    try:
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            holidays = set()
            # The API returns holidays in the 'holidays' array
            for holiday in data.get('holidays', []):
                date_str = holiday.get('date', '')
                if date_str:
                    # NSE returns date in "DD-MMM-YYYY" format (e.g., "26-Jan-2026")
                    # Convert to "YYYY-MM-DD" for consistency
                    try:
                        parsed_date = datetime.strptime(date_str, "%d-%b-%Y")
                        holidays.add(parsed_date.strftime("%Y-%m-%d"))
                    except ValueError:
                        continue
            print(f"✅ Fetched {len(holidays)} NSE holidays")
            return holidays
        else:
            print(f"⚠️ Could not fetch holidays. Status: {response.status_code}")
            return set()
    except Exception as e:
        print(f"⚠️ Error fetching holidays: {e}")
        return set()

def is_trading_day(date_str):
    """
    Check if a given date (YYYY-MM-DD) is a trading day.
    Returns False if it's a weekend or NSE holiday.
    """
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    
    # Weekends (Saturday = 5, Sunday = 6)
    if date_obj.weekday() >= 5:
        return False
    
    # Check against holiday list
    holidays = fetch_nse_holidays()
    if date_str in holidays:
        print(f"📌 {date_str} is a NSE holiday")
        return False
    
    return True

def adjust_to_previous_trading_day(date_str, max_attempts=10):
    """
    Given a date string (YYYY-MM-DD), find the most recent previous trading day.
    Moves backwards one day at a time until a trading day is found.
    """
    current_date = datetime.strptime(date_str, "%Y-%m-%d")
    
    for i in range(max_attempts):
        date_check = current_date.strftime("%Y-%m-%d")
        if is_trading_day(date_check):
            return date_check
        # Move one day back
        current_date = current_date - timedelta(days=1)
    
    # Fallback: return the original date (should not happen)
    print(f"⚠️ Could not find a trading day within {max_attempts} attempts. Using original date.")
    return date_str

def get_adjusted_expiry(original_expiry):
    """
    Main function: takes an expiry date, returns the adjusted expiry date
    (shifts to previous trading day if original is holiday/weekend).
    """
    # First, check if the original expiry is a trading day
    if is_trading_day(original_expiry):
        return original_expiry
    
    # If not, find the previous trading day
    adjusted = adjust_to_previous_trading_day(original_expiry)
    if adjusted != original_expiry:
        print(f"📅 Expiry adjusted from {original_expiry} to {adjusted} (holiday adjustment)")
    return adjusted