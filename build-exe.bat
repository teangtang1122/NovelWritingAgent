@echo off
setlocal

set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\build-exe.ps1" %*

if errorlevel 1 (
  echo.
  echo Packaging failed. See the message above.
  pause
)
