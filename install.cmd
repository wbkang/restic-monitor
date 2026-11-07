@echo off
rem Double-clickable entry point: .ps1 files can't be launched from Explorer
rem by default. Install.ps1 self-elevates via UAC on its own.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1"
if errorlevel 1 pause
