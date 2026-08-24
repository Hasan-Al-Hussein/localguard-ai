@echo off
setlocal
cd /d "%~dp0"
title LocalGuard AI - Stop

set "LOCALGUARD_PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if exist "%LOCALGUARD_PWSH%" (
  "%LOCALGUARD_PWSH%" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
) else (
  docker compose --profile app stop
)

if errorlevel 1 (
  echo.
  echo LocalGuard could not stop cleanly. Make sure Docker Desktop is running.
  pause
  exit /b 1
)

echo.
echo LocalGuard stopped. Your local documents and database were preserved.
pause
exit /b 0
