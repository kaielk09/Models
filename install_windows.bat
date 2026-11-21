@echo off
title Models Studio - Setup
cd /d "%~dp0"
echo Installing Models Studio dependencies...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Check the Python installation and try again.
  pause
  exit /b 1
)
echo.
echo Setup complete. Run run_windows.bat to launch the app.
pause
