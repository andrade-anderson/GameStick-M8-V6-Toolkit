@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Convert_CHD_Recursive_to_Root_v4.ps1"
