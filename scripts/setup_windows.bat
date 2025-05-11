@echo off
echo Setting up Telegram User Bot (Windows)...

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed! Please install Python 3.8 or newer.
    echo Download from: https://www.python.org/downloads/
    exit /b 1
)

:: Check if uv is installed
uv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Installing uv package manager...
    pip install uv
)

:: Create and activate a virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Install dependencies with uv
echo Installing dependencies...
uv pip install -r requirements.txt

echo.
echo Setup completed successfully!
echo.
echo To run the bot, use: scripts\run_windows.bat
echo.