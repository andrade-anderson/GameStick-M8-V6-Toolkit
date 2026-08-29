@echo off
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
  python DBMaker_M8_V6_v2.py
) else (
  py DBMaker_M8_V6_v2.py
)
echo.
pause
