# Maybank Manchester United Match Notifier Bot

A Telegram bot that automatically sends notifications about Manchester United matches, including upcoming fixtures, live scores, and match results. Designed for Maybank Manchester United credit card holders to optimise bonus spending based on match outcomes.

## What It Does

- **Morning Check (9:00 AM SGT)** - Checks if Manchester United have a match today, sends match details with kickoff times (UK & Singapore), betting odds from William Hill, and estimated win probability
- **Evening Check (10:45 PM SGT)** - Checks for live scores and recently finished match results
- **Match Result Notifications** - When United win, calculates remaining time for Maybank card bonus spending (valid until midnight SGT)
- **Duplicate Prevention** - Uses a 24-hour cache to avoid sending the same notification twice

## APIs Used

| API | Purpose |
|-----|---------|
| [The Odds API](https://the-odds-api.com/) | Upcoming EPL match data and betting odds |
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
│       ├── Dockerfile             # Inner Dockerfile (build context: build/docker/)
│       ├── main.py                # Main application
│       ├── debug.py               # Interactive debug/test script
│       └── requirements.txt       # Python dependencies
├── dev/                           # Development/experimental scripts
│   ├── main.py                    # Dev version of main app
│   ├── oddsapi.py                 # pytz-based version
│   ├── Football API.py            # Football Data API experiments
│   └── man-united-odds-api-script.py  # Early prototype
├── .env.example                   # Template for environment variables
└── README.md
```

## Setup

### 1. Clone and configure environment

```bash
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
# Build the image
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

This gives you an interactive menu to manually trigger morning checks, evening checks, or match result lookups.

## How It Works

The app runs inside an Alpine Linux Docker container with two cron jobs:

1. **`0 9 * * *`** - Runs `main.py` at 9:00 AM SGT to check for today's matches
2. **`45 22 * * *`** - Runs `main.py` at 10:45 PM SGT to check live scores and results

When a match is detected:
- Fetches odds from William Hill via The Odds API
- Calculates win probability using implied odds
- Sends a formatted Telegram message with match details, odds, and Maybank card spending advice
- After the match, sends result notification with time remaining for bonus spending (if United won)

## Deployment

The container runs on `docker@core.lan` and is deployed via Docker Compose. The image is published to Docker Hub as `quinneyd/mufc-match-notifier`.
