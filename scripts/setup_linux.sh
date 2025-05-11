#!/bin/bash
set -e

echo "Setting up Telegram User Bot (Linux)..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python is not installed! Please install Python 3.8 or newer."
    echo "You can install it using your distribution's package manager."
    echo "For example: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    pip3 install --user uv
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create and activate a virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies with uv
echo "Installing dependencies..."
uv pip install -r requirements.txt

echo ""
echo "Setup completed successfully!"
echo ""
echo "To run the bot, use: bash scripts/run_linux.sh"
echo ""

# Make the run script executable
chmod +x scripts/run_linux.sh 2>/dev/null || true