import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import schedule
import time
from telegram import Bot
import asyncio

# Odds API base URL and key
ODDS_API_KEY = os.environ.get('ODDS_API_KEY')
ODDS_API_BASE_URL = os.environ.get('ODDS_API_BASE_URL', 'https://api.the-odds-api.com/v4/sports')

# Manchester United team name (used for matching in Odds API data)
MAN_UNITED_NAME = "Manchester United"

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Initialize the Telegram bot
bot = Bot(TELEGRAM_BOT_TOKEN)

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

def check_upcoming_matches():
    matches = get_upcoming_matches()
    if matches:
        for match in matches:
            if MAN_UNITED_NAME in [match['home_team'], match['away_team']]:
                analyze_match(match)

def analyze_match(match):
    match_date_utc = datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00"))
    match_date_uk = match_date_utc.astimezone(ZoneInfo("Europe/London"))
    match_date_sg = match_date_utc.astimezone(ZoneInfo("Asia/Singapore"))
    
    # Estimate match end time (assuming 2 hours duration)
    match_end_uk = match_date_uk + timedelta(hours=2)
    match_end_sg = match_date_sg + timedelta(hours=2)
    
    home_team = match["home_team"]
    away_team = match["away_team"]
    is_home = home_team == MAN_UNITED_NAME
    
    win_probability, man_united_odds, opponent_odds = calculate_odds(match)
    
    # Determine the spending date in Singapore time
    spending_date = match_date_sg.date()
    
    message = f"""
Upcoming Manchester United match:
{'Home' if is_home else 'Away'} vs {away_team if is_home else home_team}
Date: {match_date_sg.strftime('%A, %d %B %Y')}

Kickoff time (UK): {match_date_uk.strftime('%I:%M %p')}
Kickoff time (Singapore): {match_date_sg.strftime('%I:%M %p')}

Estimated match end time (UK): {match_end_uk.strftime('%I:%M %p')}
Estimated match end time (Singapore): {match_end_sg.strftime('%I:%M %p')}

Odds:
Manchester United: {man_united_odds}
{away_team if is_home else home_team}: {opponent_odds}

Estimated win probability: {win_probability:.2f}%

Credit Card Spending Date (Singapore time):
{spending_date.strftime('%A, %d %B %Y')}

Recommendation: {"Consider using your Maybank Manchester United Card for purchases on this date." if win_probability > 50 else "The win probability is low. Use your card with caution on this date."}
    """
    
    send_notification(message)

def calculate_odds(match):
    man_united_odds = None
    opponent_odds = None
    
    for bookmaker in match['bookmakers']:
        for market in bookmaker['markets']:
            if market['key'] == 'h2h':
                for outcome in market['outcomes']:
                    if outcome['name'] == MAN_UNITED_NAME:
                        man_united_odds = outcome['price']
                    else:
                        opponent_odds = outcome['price']
                
                if man_united_odds and opponent_odds:
                    win_probability = (1 / man_united_odds) * 100
                    return round(win_probability, 2), man_united_odds, opponent_odds
    
    # If odds are not found, return default values
    return 50.0, 2.0, 2.0  # Default 50% probability and even odds

async def send_telegram_message(message):
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception as e:
        print(f"Error sending Telegram message: {e}")

def send_notification(message):
    print(f"Notification:\n{message}")
    # Use asyncio to run the async Telegram function
    asyncio.run(send_telegram_message(message))

def run_daily_check():
    print("Running daily check...")
    check_upcoming_matches()

if __name__ == "__main__":
    # Run the check immediately when the script starts
    run_daily_check()
    
    # Schedule the check to run daily at a specific time (e.g., 8:00 AM Singapore time)
    schedule.every().day.at("08:00").do(run_daily_check)
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Sleep for 1 minute before checking again
