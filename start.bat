@echo off
cd /d "%~dp0"
py -3 app.py
if errorlevel 1 (
  echo.
  echo Server exited with an error. Run setup.bat first if needed.
  pause
)
