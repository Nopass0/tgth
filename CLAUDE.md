# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Description

This is a Telegram user bot built with Pyrogram that allows you to send messages from your account to any chat. The bot operates on your Telegram user account (not a bot account) and provides features like sending messages to any chat, listing recent chats, and checking account status.

## Setup Commands

### Linux
```bash
# Make scripts executable
chmod +x scripts/setup_linux.sh
chmod +x scripts/run_linux.sh
chmod +x scripts/run_api_linux.sh

# Setup the environment (creates .venv)
./scripts/setup_linux.sh

# Run the bot
./scripts/run_linux.sh

# Run the API server
./scripts/run_api_linux.sh
```

### Windows
```bash
# Setup the environment
scripts\setup_windows.bat

# Run the bot
scripts\run_windows.bat

# Run the API server
scripts\run_api_windows.bat
```

## Configuration

The project uses a `.env` file for configuration with the following variables:
- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API hash
- `PHONE`: Your phone number with country code
- `LOGIN`: Session name (default: user_account or linkbot)

## Bot Architecture

The repository contains three main components:

1. `bot.py` (Link Bot):
   - Main implementation that allows creating "links" to chats
   - Stores chat links in `links.json`
   - Commands:
     - `#link [Name]` - Create a new link to a chat
     - `#list` - List all linked chats
     - `#del [Number]` - Delete a link
     - `#[Number] [Text]` - Send message to linked chat

2. `bot_new.py` (Alternative Implementation):
   - Simpler implementation with debugging features
   - Uses different command prefix (`/`)
   - Primarily handles messages and provides verbose logging

3. `api_server.py` (API Server):
   - FastAPI web server that provides HTTP endpoints for bot functionality
   - Endpoints:
     - `GET /chats` - Get a list of all available chats
     - `POST /send` - Send a message to a specific chat
   - Uses API key authentication (stored in `.api_key` file)
   - Displays server IP and port on startup
   - Auto-restarts on failure
   - Includes Swagger documentation at `/docs` endpoint

The bots are implemented using:
- Pyrogram client for Telegram API interaction
- Environment variables for configuration
- Filters for message handling 
- Global state for storing links and user information

## Dependencies

- pyrogram==2.0.106 - Telegram client library
- tgcrypto==1.2.5 - Crypto functions for Pyrogram
- python-decouple==3.8 - Environment variable handler
- python-dotenv==1.0.0 - .env file handler
- fastapi==0.109.0 - API framework for the server
- uvicorn==0.27.0 - ASGI server implementation
- pydantic==2.5.2 - Data validation and settings
- uv (for package management)

## Additional Notes

- The bot requires authentication on first run and will save the session
- Session file (`.session`) is stored in the project directory
- The project uses UV for dependency management instead of pip
- Be aware that using user bots might violate Telegram's Terms of Service