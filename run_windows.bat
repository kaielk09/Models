@echo off
setlocal
title Models Studio
cd /d "%~dp0"
if exist ".venv\\Scripts\\python.exe" (
  ".venv\\Scripts\\python.exe" main.py
) else (
  py -3 main.py
)
if errorlevel 1 (
  echo.
  echo Models Studio stopped with an error.
  pause
)
