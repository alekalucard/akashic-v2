@echo off
:: Akashic MCP Service Uninstaller
:: Right-click -> Run as Administrator

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"
echo Stopping Akashic MCP Service...
python mcp_service.py stop 2>nul
timeout /t 2 >nul
echo Removing service...
python mcp_service.py remove
echo.
echo Service removed.
pause
