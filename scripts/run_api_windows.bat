@echo off
echo Starting Telegram Bot API Server...

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Run the API server
python api_server.py