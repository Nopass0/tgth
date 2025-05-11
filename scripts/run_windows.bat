@echo off
echo Starting Telegram User Bot...

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the bot
python bot.py

:: If the script exits, keep the window open
pause