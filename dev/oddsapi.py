import os
from datetime import datetime, timedelta
import pytz
import requests
import json
from telegram import Bot
import asyncio

# API keys and URLs
ODDS_API_KEY = os.environ.get('ODDS_API_KEY')
ODDS_API_BASE_URL = os.environ.get('ODDS_API_BASE_URL', 'https://api.the-odds-api.com/v4/sports')
FOOTBALL_DATA_API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY')
FOOTBALL_DATA_BASE_URL = os.environ.get('FOOTBALL_DATA_BASE_URL', 'http://api.football-data.org/v4')

# Manchester United team details
MAN_UNITED_NAME = "Manchester United"
MAN_UNITED_ID = 66

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Initialize the Telegram bot
bot = Bot(TELEGRAM_BOT_TOKEN)

# Add these global variables at the top of your script
CACHE_FILE = 'notification_cache.json'
cache = {}

# Replace ZoneInfo usage with pytz
UK_TZ = pytz.timezone("Europe/London")
SG_TZ = pytz.timezone("Asia/Singapore")
UTC_TZ = pytz.UTC

def load_cache():
    global cache
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
    except FileNotFoundError:
        cache = {}

def save_cache():
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

async def send_notification(message, notification_type):
    global cache
    current_time = datetime.now().isoformat()
    
    if notification_type in cache:
        last_sent_time = datetime.fromisoformat(cache[notification_type]['time'])
        last_sent_message = cache[notification_type]['message']
        
        # Check if the same message was sent in the last 24 hours
        if (datetime.now() - last_sent_time) < timedelta(hours=24) and message == last_sent_message:
            print(f"Skipping duplicate {notification_type} notification")
            return

    # Send the notification
    await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    
    # Update the cache
    cache[notification_type] = {'time': current_time, 'message': message}
    save_cache()

def get_upcoming_matches():
    url = f"{ODDS_API_BASE_URL}/soccer_epl/odds"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'uk',
        'markets': 'h2h',
        'dateFormat': 'iso'
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"Failed to get data: status_code {response.status_code}, response body {response.text}")
        return None
    return response.json()

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
    matches = get_upcoming_matches()
    if matches:
        today_uk = datetime.now(UK_TZ).date()
        for match in matches:
            match_date_utc = datetime.strptime(match["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
            match_date_utc = UTC_TZ.localize(match_date_utc)
            match_date_uk = match_date_utc.astimezone(UK_TZ)
            
            if match_date_uk.date() == today_uk and MAN_UNITED_NAME in [match['home_team'], match['away_team']]:
                await analyze_match(match)
                return

async def analyze_match(match):
    match_date_utc = datetime.strptime(match["commence_time"], "%Y-%m-%dT%H:%M:%SZ")
    match_date_utc = UTC_TZ.localize(match_date_utc)
    match_date_uk = match_date_utc.astimezone(UK_TZ)
    match_date_sg = match_date_utc.astimezone(SG_TZ)
    
    # Estimate match end time (assuming 2 hours duration)
    match_end_uk = match_date_uk + timedelta(hours=2)
    match_end_sg = match_date_sg + timedelta(hours=2)
    
    home_team = match["home_team"]
    away_team = match["away_team"]
    is_home = home_team == MAN_UNITED_NAME
    
    win_probability, man_united_odds, opponent_odds = calculate_odds(match)
    
    message = f"""
🚨 Manchester United match today! 🚨
{'🏠 Home' if is_home else '🚌 Away'} vs {away_team if is_home else home_team}

🇬🇧 Kickoff time (UK): {match_date_uk.strftime('%I:%M %p')}
🇸🇬  Kickoff time (Singapore): {match_date_sg.strftime('%I:%M %p')}

⌛ Estimated match end time (UK): {match_end_uk.strftime('%I:%M %p')}
⌛ Estimated match end time (Singapore): {match_end_sg.strftime('%I:%M %p')}

📊 Odds:
Manchester United: {man_united_odds}
{away_team if is_home else home_team}: {opponent_odds}

🔮 Estimated win probability: {win_probability:.2f}%

💳 Maybank Manchester United Card Tip:
{"Consider using your card for purchases today for potential bonus points!" if win_probability > 50 else "The win probability is low. Use your card with caution today."}
    """
    
    await send_notification(message, 'upcoming_match')

def get_live_score():
    url = f"{FOOTBALL_DATA_BASE_URL}/teams/{MAN_UNITED_ID}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"status": "LIVE"}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Failed to get live score: status_code {response.status_code}, response body {response.text}")
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
        is_home = home_team == MAN_UNITED_NAME
        man_united_score = score['home'] if is_home else score['away']
        opponent_score = score['away'] if is_home else score['home']
        
        message = f"🚨 Manchester United Live Match Update! 🚨\n\n"
        message += f"⚽ Live Score: {home_team} {score['home']} - {score['away']} {away_team}\n\n"
        
        match_start_time = datetime.strptime(match['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
        match_start_time = UTC_TZ.localize(match_start_time)
        current_time = datetime.now(UTC_TZ)
        elapsed_time = current_time - match_start_time
        
        if elapsed_time.total_seconds() < 105 * 60:
            estimated_end_time = match_start_time + timedelta(minutes=105)
            estimated_end_time_sg = estimated_end_time.astimezone(SG_TZ)
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

async def check_match_result():
    url = f"{FOOTBALL_DATA_BASE_URL}/teams/{MAN_UNITED_ID}/matches"
    headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
    params = {"status": "FINISHED", "limit": 1}
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Failed to get match result: status_code {response.status_code}, response body {response.text}")
        return
    
    data = response.json()
    matches = data.get('matches', [])
    
    if matches:
        match = matches[0]
        match_date_utc = datetime.strptime(match['utcDate'], "%Y-%m-%dT%H:%M:%SZ")
        match_date_utc = UTC_TZ.localize(match_date_utc)
        match_end_time_utc = match_date_utc + timedelta(minutes=105)
        current_time_utc = datetime.now(UTC_TZ)
        
        if (current_time_utc - match_end_time_utc) <= timedelta(hours=24):
            home_team = match['homeTeam']['name']
            away_team = match['awayTeam']['name']
            score = match['score']['fullTime']
            is_home = home_team == "Manchester United FC"
            
            man_united_score = score['home'] if is_home else score['away']
            opponent_score = score['away'] if is_home else score['home']
            opponent = away_team if is_home else home_team
            
            match_date_uk = match_date_utc.astimezone(UK_TZ)
            match_date_sg = match_date_utc.astimezone(SG_TZ)
            match_end_time_sg = match_end_time_utc.astimezone(SG_TZ)
            
            result = "won" if man_united_score > opponent_score else "lost" if man_united_score < opponent_score else "drew"
            
            message = f"🚨 Manchester United Match Result! 🚨\n\n"
            message += f"⚽ Manchester United {result} their last match {man_united_score}-{opponent_score} "
            message += f"against {opponent} ({'🏠 home' if is_home else '🚌 away'}).\n\n"
            message += f"📅 Match date: {match_date_uk.strftime('%d %B %Y')}\n\n"
            message += f"⏰ Kickoff time:\n"
            message += f"   🇬🇧 UK time: {match_date_uk.strftime('%I:%M %p')}\n"
            message += f"   🇸🇬 Singapore time: {match_date_sg.strftime('%I:%M %p')}\n\n"
            message += f"⌛ End time (Singapore): {match_end_time_sg.strftime('%I:%M %p')}\n\n"
            
            message += "💳 Maybank Manchester United Card Tip:\n"
            if result == "won":
                singapore_now = datetime.now(SG_TZ)
                singapore_midnight = singapore_now.replace(hour=23, minute=59, second=59, microsecond=999999)
                time_remaining = singapore_midnight - singapore_now
                
                hours, remainder = divmod(time_remaining.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                
                time_remaining_str = f"{hours} hours and {minutes} minutes"
                
                message += "You can spend on the card now to earn bonus points and cashback!\n"
                message += "Important: Bonus spending is only valid until midnight Singapore time tonight!\n\n"
                message += f"⏳ Time remaining for bonus spending: {time_remaining_str}"
            else:
                message += "Standard points and cashback rates apply for card spending. Check your card terms for details."
            
            await send_notification(message, 'match_result')
        else:
            print("Most recent match ended more than 24 hours ago. No notification sent.")
    else:
        print("No recent Manchester United match result found.")

async def run_morning_check():
    print("Running morning check...")
    await check_upcoming_matches()

async def run_evening_check():
    print("Running evening check...")
    await check_live_score()
    await check_match_result()

async def main():
    load_cache()
    
    # Get the current time in Singapore
    singapore_time = datetime.now(SG_TZ)
    
    # Run morning check if it's close to 7:00 AM
    if singapore_time.hour == 7 and singapore_time.minute < 15:
        await run_morning_check()
    
    # Run evening check if it's close to 10:45 PM
    elif singapore_time.hour == 22 and 30 <= singapore_time.minute < 59:
        await run_evening_check()
    
    else:
        print("Not the scheduled time for checks. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())