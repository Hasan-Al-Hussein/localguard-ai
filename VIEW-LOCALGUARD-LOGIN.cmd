@echo off
setlocal
cd /d "%~dp0"
title LocalGuard AI - Demo Login
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\show-login.ps1" -Role reviewer
pause
