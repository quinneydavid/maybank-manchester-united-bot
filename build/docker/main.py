import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
import json
from telegram import Bot
import asyncio
import logging
import sys

# Manchester United name variations
MAN_UNITED_VARIATIONS = ["Manchester United", "Manchester United FC", "Man United", "Man Utd"]

# Lock file path
LOCK_FILE = '/app/logs/bot_lock.pid'

# API keys and URLs
ODDS_API_KEY = os.environ.get('ODDS_API_KEY')
ODDS_API_BASE_URL = os.environ.get('ODDS_API_BASE_URL')
FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = os.environ.get('FOOTBALL_DATA_BASE_URL')

# Manchester United team details
MAN_UNITED_NAME = "Manchester United"
MAN_UNITED_ID = 66

# Helper function to check if a team is Manchester United
def is_man_united(team_name):
    return any(variation.lower() in team_name.lower() for variation in MAN_UNITED_VARIATIONS)

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Initialize the Telegram bot
bot = Bot(TELEGRAM_BOT_TOKEN)

CACHE_FILE = '/app/logs/notification_cache.json'
cache = {}

# Function to acquire execution lock
def acquire_lock():
    try:
        # Check if lock file exists and process is still running
        if os.path.exists(LOCK_FILE):
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                # Check if process with this PID exists
                os.kill(pid, 0)
                # Process exists, another instance is running
                logger.info(f"Another instance is running with PID {pid}. Exiting.")
                return False
            except OSError:
                # Process doesn't exist, stale lock file
                logger.info("Stale lock file found. Acquiring lock.")
        
        # Create lock file with current PID
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
        return True
    except Exception as e:
        logger.error(f"Error acquiring lock: {str(e)}")
        return False

# Function to release execution lock
def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        logger.error(f"Error releasing lock: {str(e)}")

# Initialize ACTIVE_MATCH as a global variable
global ACTIVE_MATCH
ACTIVE_MATCH = None

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    file_handler = logging.FileHandler('/app/logs/oddsapi.log')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging()

def initialize_cache_file():
    try:
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

        # Create cache file with empty JSON object if it doesn't exist
        if not os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'w') as f:
                json.dump({}, f)
            logger.info(f"Created new cache file at {CACHE_FILE}")
        elif os.path.getsize(CACHE_FILE) == 0:
            with open(CACHE_FILE, 'w') as f:
                json.dump({}, f)
            logger.info(f"Initialized empty cache file at {CACHE_FILE}")
    except Exception as e:
        logger.error(f"Error initializing cache file: {str(e)}")

def load_cache():
    global cache
    try:
        # Initialize cache file if needed
        initialize_cache_file()

        # Load cache contents
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    except json.JSONDecodeError:
        logger.error(f"Error reading {CACHE_FILE}. Resetting cache.")
        cache = {}
        save_cache()  # Save empty cache to fix corrupted file
    except Exception as e:
        logger.error(f"Unexpected error loading cache: {str(e)}")
        cache = {}

def save_cache():
    try:
        # Ensure the logs directory exists
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)

        # Save cache with pretty printing for better readability
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cache: {str(e)}")

async def send_notification(message, notification_type):
    global cache
    current_time = datetime.now().isoformat()

    if notification_type in cache:
        last_sent_time = datetime.fromisoformat(cache[notification_type]['time'])
        last_sent_message = cache[notification_type]['message']

        # Prevent sending same type of notification within 30 minutes
        if (datetime.now() - last_sent_time) < timedelta(minutes=30):
            logger.info(f"Skipping {notification_type} notification - sent too recently")
            return
            
        # For identical messages, use a longer timeframe
        if message == last_sent_message and (datetime.now() - last_sent_time) < timedelta(hours=24):
            logger.info(f"Skipping duplicate {notification_type} notification")
            return

    # Send the notification
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

    # Update the cache
    cache[notification_type] = {'time': current_time, 'message': message}
    save_cache()

def get_upcoming_matches():
    try:
        url = f"{ODDS_API_BASE_URL}/soccer_epl/odds"
        params = {
            'apiKey': ODDS_API_KEY,
            'regions': 'uk',
            'markets': 'h2h',
            'dateFormat': 'iso'
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            logger.error(f"Failed to get odds data: status_code {response.status_code}, response body {response.text}")
            return None
        return response.json()
    except Exception as e:
        logger.error(f"Error fetching odds data: {str(e)}")
        return None

def calculate_odds(match):
    bookmakers = match.get('bookmakers', [])
    if not bookmakers:
        return 0, "N/A", "N/A"

    for bookmaker in bookmakers:
        if bookmaker['key'] == 'williamhill':
            markets = bookmaker.get('markets', [])
            for market in markets:
                if market['key'] == 'h2h':
                    outcomes = market.get('outcomes', [])
                    man_united_odds = next((o['price'] for o in outcomes if o['name'] == MAN_UNITED_NAME), None)
                    opponent_odds = next((o['price'] for o in outcomes if o['name'] != MAN_UNITED_NAME), None)

                    if man_united_odds and opponent_odds:
                        win_probability = (1 / man_united_odds) / ((1 / man_united_odds) + (1 / opponent_odds)) * 100
                        return win_probability, man_united_odds, opponent_odds

    return 0, "N/A", "N/A"

async def check_upcoming_matches():
    global ACTIVE_MATCH
    matches = get_upcoming_matches()
    if matches:
        today_uk = datetime.now(ZoneInfo("Europe/London")).date()
        for match in matches:
            match_date_utc = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
            match_date_uk = match_date_utc.astimezone(ZoneInfo("Europe/London"))

            if match_date_uk.date() == today_uk and MAN_UNITED_NAME in [match['home_team'], match['away_team']]:
                ACTIVE_MATCH = {
                    'start_time': match_date_utc,
                    'notified': False
                }
                await analyze_match(match)
                return

async def analyze_match(match):
    match_date_utc = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
    match_date_uk = match_date_utc.astimezone(ZoneInfo("Europe/London"))
    match_date_sg = match_date_utc.astimezone(ZoneInfo("Asia/Singapore"))

    # Estimate match end time (assuming 2 hours duration)
    match_end_uk = match_date_uk + timedelta(hours=2)
    match_end_sg = match_date_sg + timedelta(hours=2)

    home_team = match["home_team"]
    away_team = match["away_team"]
    is_home = home_team == MAN_UNITED_NAME

    # Try to get odds information if available
    win_probability, man_united_odds, opponent_odds = calculate_odds(match)

    message = f"""
🚨 Manchester United match today! 🚨
{'🏠 Home' if is_home else '🚌 Away'} vs {away_team if is_home else home_team}

📅 Match date: {match_date_uk.strftime('%d %B %Y')}

🇬🇧 UK: {match_date_uk.strftime('%d %B %Y, %I:%M %p')}
🇸🇬 Singapore: {match_date_sg.strftime('%d %B %Y, %I:%M %p')}

⌛ Estimated match end time (UK): {match_end_uk.strftime('%I:%M %p')}
⌛ Estimated match end time (Singapore): {match_end_sg.strftime('%I:%M %p')}
"""

    # Only add odds information if available and valid
    if win_probability is not None and man_united_odds != "N/A" and opponent_odds != "N/A":
        message += f"""
📊 Odds:
Manchester United: {man_united_odds}
{away_team if is_home else home_team}: {opponent_odds}

🔮 Estimated win probability: {win_probability:.2f}%

💳 Maybank Manchester United Card Tip:
{"Consider using your card for purchases today for potential bonus points!" if win_probability > 50 else "The win probability is low. Use your card with caution today."}
"""
    else:
        message += """
💳 Maybank Manchester United Card Tip:
Use your card according to the match result for potential bonus points!
"""

    await send_notification(message, 'upcoming_match')

def get_live_score():
    url = f"{FOOTBALL_DATA_BASE_URL}/teams/{MAN_UNITED_ID}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"status": "LIVE"}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        logger.error(f"Failed to get live score: status_code {response.status_code}, response body {response.text}")
        return None

    data = response.json()
    matches = data.get('matches', [])

    return matches[0] if matches else None

async def check_live_score():
    match = get_live_score()
    if match:
        home_team = match['homeTeam']['name']
        away_team = match['awayTeam']['name']
        score = match['score']['fullTime']
        
        # Use the helper function instead of direct comparison
        is_home = is_man_united(home_team)
        man_united_score = score['home'] if is_home else score['away']
        opponent_score = score['away'] if is_home else score['home']
        opponent = away_team if is_home else home_team

        message = f"🚨 Manchester United Live Match Update! 🚨\n\n"
        message += f"⚽ Live Score: {home_team} {score['home']} - {score['away']} {away_team}\n\n"

        match_start_time = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        current_time = datetime.now(ZoneInfo("UTC"))
        elapsed_time = current_time - match_start_time

        if elapsed_time.total_seconds() < 105 * 60:
            estimated_end_time = match_start_time + timedelta(minutes=105)
            estimated_end_time_sg = estimated_end_time.astimezone(ZoneInfo("Asia/Singapore"))
            message += f"⏰ Estimated end time: {estimated_end_time_sg.strftime('%I:%M %p')} (Singapore time)\n\n"
        else:
            message += "⏰ The match is in extra time or has been delayed.\n\n"

        message += "📊 Current Status:\n"
        if man_united_score > opponent_score:
            message += "Manchester United is winning! High chance you can spend on the card.\n\n"
        elif man_united_score == opponent_score:
            message += "The match is currently tied. Spend with caution.\n\n"
        else:
            message += "Manchester United is currently behind. It's risky to spend on the card now.\n\n"

        message += "💳 Maybank Manchester United Card Tip:\n"
        message += "Remember, bonus spending is only valid until midnight Singapore time!"

        await send_notification(message, 'live_score')

# Helper function to calculate time remaining until midnight
def calculate_time_remaining():
    # Use current date for midnight calculation, not match date
    singapore_now = datetime.now(ZoneInfo("Asia/Singapore"))
    singapore_midnight = datetime(
        singapore_now.year, 
        singapore_now.month, 
        singapore_now.day, 
        23, 59, 59, 999999, 
        tzinfo=ZoneInfo("Asia/Singapore")
    )
    
    time_remaining = singapore_midnight - singapore_now
    
    hours, remainder = divmod(time_remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if hours > 0:
        time_remaining_str = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
    else:
        time_remaining_str = f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    return time_remaining_str

async def check_match_result():
    url = f"{FOOTBALL_DATA_BASE_URL}/teams/{MAN_UNITED_ID}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"status": "FINISHED", "limit": 1}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        logger.error(f"Failed to get match result: status_code {response.status_code}, response body {response.text}")
        return False

    data = response.json()
    matches = data.get('matches', [])

    if matches:
        match = matches[0]
        match_date_utc = datetime.fromisoformat(match['utcDate'].replace('Z', '+00:00'))
        match_end_time_utc = match_date_utc + timedelta(minutes=105)
        current_time_utc = datetime.now(ZoneInfo("UTC"))

        # Check if match ended in last 2 hours
        if (current_time_utc - match_end_time_utc) <= timedelta(hours=2):
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            score = match['score']['fullTime']
            
            # Use the helper function instead of direct comparison
            is_home = is_man_united(home_team)

            man_united_score = score['home'] if is_home else score['away']
            opponent_score = score['away'] if is_home else score['home']
            opponent = away_team if is_home else home_team

            match_date_uk = match_date_utc.astimezone(ZoneInfo("Europe/London"))
            match_date_sg = match_date_utc.astimezone(ZoneInfo("Asia/Singapore"))
            match_end_time_sg = match_end_time_utc.astimezone(ZoneInfo("Asia/Singapore"))

            result = "won" if man_united_score > opponent_score else "lost" if man_united_score < opponent_score else "drew"

            message = f"🚨 Manchester United Match Result! 🚨\n\n"
            message += f"⚽ Manchester United {result} their last match {man_united_score}-{opponent_score} "
            message += f"against {opponent} ({'🏠 home' if is_home else '🚌 away'}).\n\n"
            message += f"📅 Match date: {match_date_uk.strftime('%d %B %Y')}\n\n"
            message += f"⏰ Kickoff time:\n"
            message += f"   🇬🇧 UK time: {match_date_uk.strftime('%I:%M %p')}\n"
            message += f"   🇸🇬 Singapore time: {match_date_sg.strftime('%I:%M %p')}\n\n"
            message += f"⌛ End time (Singapore): {match_end_time_sg.strftime('%I:%M %p')}\n\n"

            if result == "won":
                singapore_now = datetime.now(ZoneInfo("Asia/Singapore"))
                
                # Check if we're still on the same day in Singapore time
                singapore_midnight = datetime(
                    singapore_now.year, 
                    singapore_now.month, 
                    singapore_now.day, 
                    23, 59, 59, 999999, 
                    tzinfo=ZoneInfo("Asia/Singapore")
                )

                # Check if we're still before midnight
                if singapore_now <= singapore_midnight:
                    time_remaining_str = calculate_time_remaining()

                    message += "💳 Maybank Manchester United Card Tip:\n"
                    message += "You can spend on the card now to earn bonus points and cashback!\n"
                    message += "Important: Bonus spending is only valid until midnight Singapore time tonight!\n\n"
                    message += f"⏳ Time remaining for bonus spending: {time_remaining_str}"
                else:
                    message += "💳 Maybank Manchester United Card Tip:\n"
                    message += "The bonus spending period for this match has ended (midnight Singapore time).\n"
                    message += "Standard points and cashback rates now apply."
            else:
                message += "💳 Maybank Manchester United Card Tip:\n"
                message += "Standard points and cashback rates apply for card spending. Check your card terms for details."

            await send_notification(message, 'match_result')
            return True

    return False

async def run_morning_check():
    logger.info("Running morning check...")
    await check_upcoming_matches()

async def run_evening_check():
    logger.info("Running evening check...")
    await check_live_score()
    await check_match_result()

async def main():
    global ACTIVE_MATCH
    logger.info("Script started")
    
    # Try to acquire lock
    if not acquire_lock():
        logger.info("Could not acquire lock. Exiting.")
        return
    
    try:
        # Initialize and load cache at startup
        initialize_cache_file()
        load_cache()

        # Get the current time in Singapore
        singapore_time = datetime.now(ZoneInfo("Asia/Singapore"))

        # Morning checks (9:00 AM SGT)
        if singapore_time.hour == 9 and singapore_time.minute < 15:
            logger.info("Starting morning check at 9:00 AM SGT")
            await run_morning_check()
            await check_match_result()

        # Regular evening check (10:45 PM SGT)
        elif singapore_time.hour == 22 and 45 <= singapore_time.minute < 60:
            logger.info("Starting evening check at 10:45 PM SGT")
            await run_evening_check()

        # Check for match end at specific intervals if there's an active match
        elif ACTIVE_MATCH and not ACTIVE_MATCH['notified']:
            current_time = datetime.now(ZoneInfo("UTC"))
            match_start = ACTIVE_MATCH['start_time']
            minutes_since_start = (current_time - match_start).total_seconds() / 60

            # Check at specific times:
            # 1. 90 minutes (normal time)
            # 2. 105 minutes (potential extra time)
            # 3. 120 minutes (maximum time)
            if minutes_since_start in range(90, 92) or \
               minutes_since_start in range(105, 107) or \
               minutes_since_start in range(120, 122):
                result = await check_match_result()
                if result:
                    ACTIVE_MATCH['notified'] = True

        else:
            logger.info("Not the scheduled time for checks. Exiting.")
    finally:
        # Always release lock when done
        release_lock()
        
    logger.info("Script finished")

if __name__ == "__main__":
    asyncio.run(main())
