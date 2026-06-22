import os
import json
import requests
from datetime import datetime, timedelta

CACHE_FILE = "holidays_cache.json"
CACHE_MAX_AGE_DAYS = 7  # Refresh once a week (change to 30 for monthly)

def fetch_nse_holidays_from_api():
    """Fetch holidays from NSE official API."""
    try:
        url = "https://www.nseindia.com/api/holiday-master?type=trading"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            holidays = set()
            for item in data.get("holidays", []):
                date_str = item.get("date", "")
                if date_str:
                    # Convert "DD-MMM-YYYY" to "YYYY-MM-DD"
                    try:
                        parsed = datetime.strptime(date_str, "%d-%b-%Y")
                        holidays.add(parsed.strftime("%Y-%m-%d"))
                    except ValueError:
                        continue
            print(f"✅ Fetched {len(holidays)} holidays from NSE API")
            return holidays
        else:
            print(f"⚠️ API returned {resp.status_code}, using cache if available")
            return None
    except Exception as e:
        print(f"⚠️ Error fetching holidays: {e}")
        return None

def load_cached_holidays():
    """Load holidays from cache file if it exists and is fresh."""
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
    """Save holidays to cache file."""
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
    """Main function – returns a set of holiday dates (YYYY-MM-DD)."""
    # Try cache first
    holidays = load_cached_holidays()
    if holidays is not None:
        return holidays
    
    # Cache missing or stale – fetch from API
    print("🌐 Fetching fresh holiday list from NSE...")
    holidays = fetch_nse_holidays_from_api()
    if holidays is not None:
        save_cache(holidays)
        return holidays
    
    # Fallback: return an empty set (no holiday adjustment)
    print("⚠️ No holiday data available – continuing without adjustments")
    return set()

def is_trading_day(date_str):
    """Check if a date is a trading day (weekday and not a holiday)."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    if date_obj.weekday() >= 5:  # Saturday or Sunday
        return False
    holidays = get_holidays()
    return date_str not in holidays

def adjust_to_previous_trading_day(date_str, max_attempts=10):
    """Move backwards until a trading day is found."""
    current = datetime.strptime(date_str, "%Y-%m-%d")
    for _ in range(max_attempts):
        check = current.strftime("%Y-%m-%d")
        if is_trading_day(check):
            return check
        current -= timedelta(days=1)
    print(f"⚠️ Could not find trading day for {date_str} – using original")
    return date_str

def get_adjusted_expiry(original_expiry):
    """Return adjusted expiry (previous trading day if original is holiday/weekend)."""
    if is_trading_day(original_expiry):
        return original_expiry
    adjusted = adjust_to_previous_trading_day(original_expiry)
    if adjusted != original_expiry:
        print(f"📅 Expiry adjusted: {original_expiry} → {adjusted}")
    return adjusted