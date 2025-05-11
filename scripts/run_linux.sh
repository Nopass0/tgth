#!/bin/bash
set -e

echo "Starting Telegram User Bot..."

# Activate virtual environment
source venv/bin/activate

# Run the bot
python3 bot.py