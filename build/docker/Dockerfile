FROM --platform=$BUILDPLATFORM python:3.11-alpine AS builder

# Install required system dependencies
RUN apk add --no-cache gcc musl-dev linux-headers python3-dev

# Set the working directory in the container
WORKDIR /app

# Install Python dependencies
RUN pip install --no-cache-dir \
    requests==2.31.0 \
    python-telegram-bot==20.6 \
    pytz==2023.3 \
    python-dotenv==1.0.0 \
    aiohttp==3.8.5 \
    asyncio==3.4.3 \
    tzdata

FROM --platform=$TARGETPLATFORM python:3.11-alpine

# Install required system dependencies
RUN apk add --no-cache dcron tzdata

# Set the working directory in the container
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# Copy the application files
COPY . .

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

# Create a cron file
RUN echo "0 9 * * * /usr/local/bin/python /app/main.py >> /tmp/out.log 2>&1" > /app/mycron && \
    echo "45 22 * * * /usr/local/bin/python /app/main.py >> /tmp/out.log 2>&1" >> /app/mycron

# Set permissions and install cron job
RUN chmod 0644 /app/mycron && \
    crontab /app/mycron

# Create log file with initial content
RUN echo "Container started at $(date)" > /tmp/out.log && chmod 666 /tmp/out.log

# Set the timezone using an environment variable
ENV TZ=Asia/Singapore

# Start cron and tail the log
CMD ["sh", "-c", "crond && (echo \"Cron daemon started at $(date)\" >> /tmp/out.log && tail -f /tmp/out.log)"]
