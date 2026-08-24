@echo off
setlocal
cd /d "%~dp0"
title LocalGuard AI - First Run and Start

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\first-run-windows.ps1"
set "LOCALGUARD_EXIT=%ERRORLEVEL%"

if not "%LOCALGUARD_EXIT%"=="0" (
  echo.
  echo LocalGuard did not finish starting. Read the message above, then run this file again.
  pause
  exit /b %LOCALGUARD_EXIT%
)

echo.
echo LocalGuard is ready at http://localhost:3000
echo Run VIEW-LOCALGUARD-LOGIN.cmd if you need a demo account password.
pause
exit /b 0
