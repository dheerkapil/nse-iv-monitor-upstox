import os
import json
import requests
from datetime import datetime, timedelta

CACHE_FILE = "holidays_cache.json"
CACHE_MAX_AGE_DAYS = 7

def fetch_nse_holidays_from_api():
    """Fetch holidays from NSE official API with session cookies."""
    try:
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        resp = session.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            holidays = set()
            for item in data.get("holidays", []):
                date_str = item.get("date", "")
                if date_str:
                    try:
                        parsed = datetime.strptime(date_str, "%d-%b-%Y")
                        holidays.add(parsed.strftime("%Y-%m-%d"))
                    except ValueError:
                        continue
            print(f"✅ Fetched {len(holidays)} holidays from NSE API")
            return holidays
        else:
            print(f"⚠️ API returned {resp.status_code}")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching holidays: {e}")
        return None

def get_static_fallback_holidays():
    """Minimal static list of fixed NSE holidays."""
    return {
        "2026-01-26", "2026-03-03", "2026-04-03", "2026-04-14",
        "2026-05-28", "2026-08-15", "2026-10-02", "2026-12-25",
        "2027-01-26", "2027-03-22", "2027-04-02", "2027-04-14",
        "2027-10-02", "2027-12-25",
    }

def load_cached_holidays():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                data = json.load(f)
                cache_time = datetime.fromisoformat(data.get("fetched_at", ""))
                age = (datetime.now() - cache_time).days
                if age < CACHE_MAX_AGE_DAYS:
                    print(f"📂 Using cached holidays (fetched {age} days ago)")
                    return set(data.get("holidays", []))
                else:
                    print(f"⏰ Cache is {age} days old – refreshing...")
        except Exception as e:
            print(f"⚠️ Cache read error: {e}")
    return None

def save_cache(holidays):
    try:
        data = {
            "fetched_at": datetime.now().isoformat(),
            "holidays": list(holidays)
        }
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
        print("💾 Holiday cache saved")
    except Exception as e:
        print(f"⚠️ Could not save cache: {e}")

def get_holidays():
    holidays = load_cached_holidays()
    if holidays is not None:
        return holidays
    
    print("🌐 Fetching fresh holiday list from NSE...")
    holidays = fetch_nse_holidays_from_api()
    if holidays and len(holidays) > 0:
        save_cache(holidays)
        return holidays
    
    print("⚠️ Using static fallback holiday list")
    return get_static_fallback_holidays()

def is_trading_day(date_str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    if date_obj.weekday() >= 5:
        return False
    holidays = get_holidays()
    return date_str not in holidays

def adjust_to_previous_trading_day(date_str, max_attempts=10):
    current = datetime.strptime(date_str, "%Y-%m-%d")
    for _ in range(max_attempts):
        check = current.strftime("%Y-%m-%d")
        if is_trading_day(check):
            return check
        current -= timedelta(days=1)
    print(f"⚠️ Could not find trading day for {date_str} – using original")
    return date_str

def get_adjusted_expiry(original_expiry):
    if is_trading_day(original_expiry):
        return original_expiry
    adjusted = adjust_to_previous_trading_day(original_expiry)
    if adjusted != original_expiry:
        print(f"📅 Expiry adjusted: {original_expiry} → {adjusted}")
    return adjusted