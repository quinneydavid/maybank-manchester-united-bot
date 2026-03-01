import os
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import schedule
import time
from telegram import Bot
import asyncio

# API base URL
BASE_URL = os.environ.get('FOOTBALL_DATA_BASE_URL', 'http://api.football-data.org/v4')

# Your API key
API_KEY = os.environ.get('FOOTBALL_DATA_API_KEY')

# Manchester United team ID
MAN_UNITED_ID = 66

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Initialize the Telegram bot
bot = Bot(TELEGRAM_BOT_TOKEN)

def check_upcoming_matches():
    # Check for matches in the next 7 days
    start_date = datetime.now(ZoneInfo("Asia/Singapore")).date()
    end_date = start_date + timedelta(days=7)
    
    headers = {"X-Auth-Token": API_KEY}
    matches_url = f"{BASE_URL}/teams/{MAN_UNITED_ID}/matches"
    params = {
        "dateFrom": start_date.isoformat(),
        "dateTo": end_date.isoformat(),
        "competitions": "PL"  # Premier League competition code
    }
    
    response = requests.get(matches_url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        matches = data.get("matches", [])
        
        for match in matches:
            analyze_match(match)
    else:
        print(f"Error accessing the API: {response.status_code}")

def analyze_match(match):
    match_date_utc = datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00"))
    match_date_uk = match_date_utc.astimezone(ZoneInfo("Europe/London"))
    match_date_sg = match_date_utc.astimezone(ZoneInfo("Asia/Singapore"))
    
    # Estimate match end time (assuming 2 hours duration)
    match_end_uk = match_date_uk + timedelta(hours=2)
    match_end_sg = match_date_sg + timedelta(hours=2)
    
    home_team = match["homeTeam"]["name"]
    away_team = match["awayTeam"]["name"]
    is_home = match["homeTeam"]["id"] == MAN_UNITED_ID
    
    win_probability = calculate_win_probability(match)
    
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

Estimated win probability: {win_probability:.2f}%

Credit Card Spending Date (Singapore time):
{spending_date.strftime('%A, %d %B %Y')}

Recommendation: {"Consider using your Maybank Manchester United Card for purchases on this date." if win_probability > 50 else "The win probability is low. Use your card with caution on this date."}
    """
    
    send_notification(message)
    
    # Schedule a post-match check
    schedule_post_match_check(match["id"], match_end_sg)

def calculate_win_probability(match):
    odds = match.get("odds", {})
    
    if not odds:
        return 50.0  # Default to 50% if no odds are available
    
    # Check if Manchester United is home or away
    is_home = match["homeTeam"]["id"] == MAN_UNITED_ID
    
    if is_home:
        man_united_odds = odds.get("homeWin", 2.0)  # Default to 2.0 if not available
    else:
        man_united_odds = odds.get("awayWin", 2.0)  # Default to 2.0 if not available
    
    # Convert odds to probability
    probability = (1 / man_united_odds) * 100
    
    # Round to two decimal places
    return round(probability, 2)

def schedule_post_match_check(match_id, end_time):
    # Schedule the post-match check 5 minutes after the estimated end time
    check_time = end_time + timedelta(minutes=5)
    schedule.every().day.at(check_time.strftime("%H:%M")).do(post_match_check, match_id=match_id)

def post_match_check(match_id):
    headers = {"X-Auth-Token": API_KEY}
    match_url = f"{BASE_URL}/matches/{match_id}"
    
    response = requests.get(match_url, headers=headers)
    
    if response.status_code == 200:
        match_data = response.json()
        if match_data["status"] == "FINISHED":
            winner = match_data["score"]["winner"]
            if (winner == "HOME_TEAM" and match_data["homeTeam"]["id"] == MAN_UNITED_ID) or \
               (winner == "AWAY_TEAM" and match_data["awayTeam"]["id"] == MAN_UNITED_ID):
                send_win_notification(match_data)
    else:
        print(f"Error accessing the API for post-match check: {response.status_code}")

def send_win_notification(match_data):
    home_team = match_data["homeTeam"]["name"]
    away_team = match_data["awayTeam"]["name"]
    score = match_data["score"]["fullTime"]
    match_date_sg = datetime.fromisoformat(match_data["utcDate"].replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Singapore"))
    spending_date = match_date_sg.date()
    
    message = f"""
Manchester United Win Alert!

{home_team} {score['home']} - {score['away']} {away_team}

Don't forget to use your Maybank Manchester United Card today for bonus cashback and air miles!

Credit Card Spending Date (Singapore time):
{spending_date.strftime('%A, %d %B %Y')}
    """
    
    send_notification(message)

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