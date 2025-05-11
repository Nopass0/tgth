# Telegram User Bot

A Telegram user bot built with Pyrogram that allows you to send messages from your account to any chat.

## Features

- Runs on your Telegram user account (not a bot account)
- Send messages to any chat from your account using commands
- List your recent chats with IDs for easy reference
- Check your account status
- Easy to set up on both Windows and Linux
- Uses UV for dependency management

## Setup

### Windows Setup

1. Make sure Python 3.8 or newer is installed.
2. Run the setup script:
   ```
   scripts\setup_windows.bat
   ```
3. Edit the `.env` file to update your configuration if needed.

### Linux Setup

1. Make sure Python 3.8 or newer is installed.
2. Make the setup script executable:
   ```
   chmod +x scripts/setup_linux.sh
   ```
3. Run the setup script:
   ```
   ./scripts/setup_linux.sh
   ```
4. Edit the `.env` file to update your configuration if needed.

## Running the Bot

### Windows
```
scripts\run_windows.bat
```

### Linux
```
./scripts/run_linux.sh
```

## Configuration

All configuration is stored in the `.env` file:

- `API_ID`: Your Telegram API ID
- `API_HASH`: Your Telegram API hash
- `PHONE`: Your phone number with country code
- `LOGIN`: Session name (default: user_account)

## Usage

Once the bot is running, you can send a message to your own Telegram account to interact with it. The bot supports the following commands:

- `/help` - Show a list of all available commands
- `/send @username Message text` - Send a message to a specified chat or user
- `/send -100123456789 Message text` - Send a message to a group chat using its ID
- `/chats` - Show a list of your 20 most recent chats with their IDs
- `/status` - Show your account information

## First Login

When you first run the bot, you'll need to authenticate:

1. You'll be prompted to enter your phone number (even though it's in the config)
2. Enter the verification code sent to your Telegram account
3. If you have two-factor authentication enabled, enter your password

After successful authentication, your session will be saved and you won't need to log in again.

## Notes

- This is a user bot that runs on your personal Telegram account
- Using user bots might violate Telegram's Terms of Service
- Use responsibly and at your own risk