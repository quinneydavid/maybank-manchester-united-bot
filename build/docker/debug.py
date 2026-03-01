import asyncio
import os
from main import run_morning_check, run_evening_check, check_match_result, load_cache

async def debug_run():
    """Debug function to manually run checks"""
    print("Loading cache...")
    load_cache()
    
    while True:
        print("\nSelect a check to run:")
        print("1. Morning Check (Upcoming Matches)")
        print("2. Evening Check (Live Score & Results)")
        print("3. Match Result Check")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ")
        
        if choice == "1":
            print("\nRunning morning check...")
            await run_morning_check()
        elif choice == "2":
            print("\nRunning evening check...")
            await run_evening_check()
        elif choice == "3":
            print("\nChecking match result...")
            await check_match_result()
        elif choice == "4":
            print("\nExiting debug mode...")
            break
        else:
            print("\nInvalid choice. Please try again.")
        
        print("\nCheck completed.")

if __name__ == "__main__":
    # Verify environment variables are set
    required_vars = [
        'ODDS_API_KEY',
        'ODDS_API_BASE_URL',
        'FOOTBALL_DATA_API_KEY',
        'FOOTBALL_DATA_BASE_URL',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_CHAT_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print("Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        exit(1)
    
    print("Starting debug mode...")
    asyncio.run(debug_run())
