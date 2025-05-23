#!/bin/bash
set -e

echo "Starting Telegram User Bot..."

# Check for virtual environment and activate
if [ -d ".venv" ]; then
    echo "Using .venv virtual environment"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo "Using venv virtual environment"
    source venv/bin/activate
else
    echo "No virtual environment found. Using system Python."
fi

# Run the bot
python3 bot.py