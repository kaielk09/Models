@echo off
setlocal
title Models Studio - EXE Build
cd /d "%~dp0"
if not exist ".venv\\Scripts\\python.exe" (
  echo Run install_windows.bat first to install dependencies.
  pause
  exit /b 1
)
".venv\\Scripts\\python.exe" -m pip install pyinstaller
if errorlevel 1 goto failed
echo Building desktop executable...
".venv\\Scripts\\python.exe" -m PyInstaller --noconfirm --clean --windowed --name "Models Studio" --collect-all pyvista --collect-all pyvistaqt --collect-all vtk --collect-all trimesh main.py
if errorlevel 1 goto failed
echo.
echo Build attempt complete. Check the dist folder.
echo Note: Packaging may require fixes on a real Windows machine.
pause
exit /b 0
:failed
echo.
echo Build failed. See messages above for the packaging error.
pause
exit /b 1
