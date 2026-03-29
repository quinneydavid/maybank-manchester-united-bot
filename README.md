# Maybank Manchester United Match Notifier Bot

A Telegram bot that helps Maybank Manchester United credit card holders maximise their miles earnings by sending timely notifications about EPL match results.

## Why This Exists

The [Maybank Manchester United Card](https://www.maybank2u.com.sg/en/personal/cards/credit/maybank-manchester-united-credit-debit.page?) has a unique rewards mechanic tied to Manchester United's EPL results:

| Match Result | Earn Rate | Cap |
|-------------|-----------|-----|
| **Man Utd Win** | 2.8 mpd (SGD & FCY) | S$2,000 per win |
| **Man Utd Draw** | 1.6 mpd (SGD & FCY) | S$2,000 per draw, max 1 draw/month |
| **Man Utd Loss / Regular Day** | 1.12 mpd (SGD & FCY) | No cap |
| **Selected Categories (SGD)** | 0.4 mpd | No cap |

The bonus earning window is **the same calendar day in Singapore time** (12:00 AM - 11:59 PM SGT). Since the UK is 7-8 hours behind Singapore, most EPL matches finish late at night SGT, leaving a narrow window to spend before midnight.

**The catch:** You're gambling. Most matches finish after 11 PM SGT, so you either spend before knowing the result, or you have very little time after the final whistle to hit S$2,000.

This bot solves that by sending real-time notifications to a Telegram group so you know exactly when to spend and how much time you have left.

### Selected Categories (reduced earn rate)

These MCCs earn only 0.4 mpd in SGD regardless of match result:
- Real estate/rentals (6513)
- Education (8211, 8220, 8241, 8244, 8249, 8299)
- Medical/hospitals/pharmacies (8062, 4119, 5047, 5122, 5912, 5975, 5976, 8011, 8021, 8031, 8041, 8042, 8043, 8049, 8050, 8071, 8099)
- Business services (7399)
- Utilities (4900)
- Telecommunications (4812, 4814)

FCY spend on these categories still benefits from match result bonuses.

## What the Bot Does

### Morning Check (9:00 AM SGT)
- Checks if Manchester United have an EPL match today
- Sends match details: kickoff time (UK & SGT), estimated end time
- Fetches betting odds from William Hill and calculates win probability
- Gives a spending recommendation based on the odds

### Evening Check (10:45 PM SGT)
- Checks for live scores during the match
- After the match, sends the result with a spending recommendation
- If United won: calculates time remaining until midnight SGT for bonus spending
- If United drew: reminds about the 1.6 mpd rate and the 1 draw/month cap

### Example Notifications

**Pre-match (9:00 AM):**
```
Manchester United match today!
Home vs Crystal Palace

UK: 01 March 2026, 02:00 PM
Singapore: 01 March 2026, 10:00 PM

Odds: Man Utd 1.5 / Crystal Palace 5.5
Win probability: 78.57%

Maybank Card Tip: Consider using your card for purchases today!
```

**Post-match (after a win):**
```
Manchester United won 3-1 against Crystal Palace (home).

Maybank Card Tip:
Spend on the card now to earn 2.8 mpd!
Bonus spending valid until midnight Singapore time tonight!

Time remaining for bonus spending: 1 hour and 14 minutes
```

## APIs Used

| API | Purpose |
|-----|---------|
| [The Odds API](https://the-odds-api.com/) | Upcoming EPL match data and William Hill betting odds |
| [Football Data API](https://www.football-data.org/) | Live scores and match results |
| [Telegram Bot API](https://core.telegram.org/bots/api) | Sending notifications to a Telegram group |

## Project Structure

```
.
├── build/
│   ├── Dockerfile                 # Outer Dockerfile (build context: build/)
│   ├── compose.yaml               # Production Docker Compose
│   ├── docker-compose.test.yaml   # Test Docker Compose
│   └── docker/
│       ├── Dockerfile             # Main Dockerfile (build context: build/docker/)
│       ├── main.py                # Main application
│       ├── debug.py               # Interactive debug/test script
│       └── requirements.txt       # Python dependencies
├── dev/                           # Development/experimental scripts
├── .env.example                   # Template for environment variables
└── README.md
```

## Setup

### 1. Clone and configure environment

```bash
git clone https://github.com/quinneydavid/maybank-manchester-united-bot.git
cd maybank-manchester-united-bot
cp .env.example .env
# Edit .env with your actual API keys and tokens
```

### 2. Required environment variables

| Variable | Description |
|----------|-------------|
| `ODDS_API_KEY` | API key from [the-odds-api.com](https://the-odds-api.com/) |
| `ODDS_API_BASE_URL` | `https://api.the-odds-api.com/v4/sports` |
| `FOOTBALL_DATA_API_KEY` | API key from [football-data.org](https://www.football-data.org/) |
| `FOOTBALL_DATA_BASE_URL` | `http://api.football-data.org/v4` |
| `TELEGRAM_BOT_TOKEN` | Bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Target Telegram group/chat ID |

### 3. Build and run with Docker

```bash
cd build/docker
docker build -t quinneyd/mufc-match-notifier:latest .

# Run with Docker Compose (from build/ directory)
cd ..
docker compose --env-file .env up -d
```

### 4. Debug / manual testing

```bash
docker exec -it mufc-match-notifier python /app/debug.py
```

Interactive menu to manually trigger morning checks, evening checks, or match result lookups.

## How It Works

The app runs inside an Alpine Linux Docker container with two cron jobs:

| Cron | Time (SGT) | What it does |
|------|-----------|--------------|
| `0 9 * * *` | 9:00 AM | Check for today's match, fetch odds, send pre-match notification |
| `45 22 * * *` | 10:45 PM | Check live score, fetch result, send spending recommendation |

The 10:45 PM timing is chosen because most 3:00 PM UK kickoffs finish around 10:45-11:00 PM SGT, giving you the result with enough time to spend before midnight.

### Concurrency protection

A PID-based lock file (`/app/logs/bot_lock.pid`) prevents multiple instances from running simultaneously.

### Duplicate prevention

A notification cache tracks what was sent and when:
- Same notification type blocked for 30 minutes
- Identical messages blocked for 24 hours

## Deployment

The image is published to Docker Hub as `quinneyd/mufc-match-notifier` and deployed via Docker Compose.

```bash
# Pull latest and redeploy
docker compose pull && docker compose up -d
```
