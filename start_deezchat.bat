@echo off
:: DeezChat Startup Script for Windows
:: This script activates the virtual environment and launches DeezChat

setlocal enabledelayedexpansion

:: Get the directory where this script is located
set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%deezchat_venv
set DEEZCHAT_BIN=%VENV_DIR%\Scripts\deezchat.exe

echo ==================================================
echo     DeezChat - BitChat Python Client
echo ==================================================
echo.

:: Check if virtual environment exists
if not exist "%VENV_DIR%" (
    echo [ERROR] Virtual environment not found at: %VENV_DIR%
    echo [ERROR] Please run: pip install -e ".[dev,test]" first
    pause
    exit /b 1
)

:: Check if deezchat binary exists
if not exist "%DEEZCHAT_BIN%" (
    echo [ERROR] DeezChat binary not found at: %DEEZCHAT_BIN%
    echo [ERROR] Virtual environment may be corrupted. Please reinstall:
    echo   rmdir /s /q %VENV_DIR%
    echo   python -m venv %VENV_DIR%
    echo   %VENV_DIR%\Scripts\activate
    echo   pip install -e ".[dev,test]"
    pause
    exit /b 1
)

echo [INFO] Virtual environment found: %VENV_DIR%
echo [INFO] Starting DeezChat application...
echo.

:: Launch the application
"%DEEZCHAT_BIN%" %*