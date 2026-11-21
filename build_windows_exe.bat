@echo off
title Models Studio - EXE Builder
cd /d "%~dp0"
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --clean --windowed --name "Models Studio" main.py
if errorlevel 1 (
  echo.
  echo Build failed. PyVista/Qt packaging may require additional configuration.
  pause
  exit /b 1
)
echo.
echo EXE output is in the dist folder.
pause
