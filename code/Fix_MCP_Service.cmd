@echo off
:: Self-elevate to admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "F:\Sandbox\failure_factory\akashic_v2"
echo.
echo ========================================
echo   AKASHIC MCP SERVICE FIX
echo ========================================
echo.

echo [1/4] Stopping any existing service...
sc stop AkashicMCP >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/4] Removing broken service...
sc delete AkashicMCP >nul 2>&1
timeout /t 2 /nobreak >nul

echo [3/4] Killing any orphan processes on port 8765...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8765" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo [4/4] Installing service with venv Python...
"F:\Sandbox\failure_factory\akashic_v2\.venv\Scripts\python.exe" mcp_service.py install
"F:\Sandbox\failure_factory\akashic_v2\.venv\Scripts\python.exe" mcp_service.py start

echo.
echo ========================================
timeout /t 2 /nobreak >nul

:: Verify
sc query AkashicMCP | findstr "RUNNING" >nul
if %errorlevel% equ 0 (
    echo   SUCCESS - Service is running
    echo   Endpoint: http://127.0.0.1:8765/sse
) else (
    echo   WARNING - Service may not have started
    echo   Check services.msc for details
)
echo ========================================
echo.
pause
