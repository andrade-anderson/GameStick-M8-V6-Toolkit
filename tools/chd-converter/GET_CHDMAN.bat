@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Get CHDMAN from the official MAME release
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Get_CHDMAN.ps1"

echo.
pause
endlocal
