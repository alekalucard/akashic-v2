@echo off
title Akashic MCP SSE Server (Persistent)
cd /d "F:\Sandbox\failure_factory\akashic_v2"

echo ============================================================
echo   AKASHIC MCP SSE SERVER - Persistent Background Service
echo   Port: 8770  (server.py uses 8765)
echo   Auto-restart on crash
echo ============================================================
echo.

:restart_loop
echo [%date% %time%] Starting MCP SSE Server...
"F:\Sandbox\venv314t\Scripts\python.exe" mcp_sse_server.py --port 8770
echo.
echo [%date% %time%] Server exited. Restarting in 5 seconds...
echo   (Press Ctrl+C to stop permanently)
timeout /t 5 /nobreak >nul
goto restart_loop
