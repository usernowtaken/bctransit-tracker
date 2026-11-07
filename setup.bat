@echo off
cd /d "%~dp0"
echo Installing BC Transit Live's GTFS decoder...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Installation failed. Make sure Python 3.10+ is installed and on PATH.
  pause
  exit /b 1
)
echo.
echo Setup complete. Double-click start.bat to launch the map.
pause
