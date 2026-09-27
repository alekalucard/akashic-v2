@echo off
:: Akashic MCP Service Installer
:: Right-click -> Run as Administrator

:: Check for admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run the PowerShell installer
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0Install_Akashic_Service.ps1"
