@echo off
cd /d "%~dp0"
echo Building GameStick_M8_V6_Toolkit_v3.exe
echo =========================================
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -m pip install --upgrade pyinstaller
    py -m PyInstaller --clean --onefile --console --name GameStick_M8_V6_Toolkit_v3 GameStick_M8_V6_Toolkit_v3.py
) else (
    python -m pip install --upgrade pyinstaller
    python -m PyInstaller --clean --onefile --console --name GameStick_M8_V6_Toolkit_v3 GameStick_M8_V6_Toolkit_v3.py
)

echo.
echo If the build succeeded, the EXE is here:
echo dist\GameStick_M8_V6_Toolkit_v3.exe
echo.
pause
