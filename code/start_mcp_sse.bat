@echo off
title Akashic MCP SSE Server - Always On
cd /d "F:\Sandbox\failure_factory\akashic_v2"
echo ========================================
echo   AKASHIC MCP SSE SERVER
echo   Always-on with auto-restart
echo ========================================
echo.
echo Starting on port 8765...
echo.
"F:\Sandbox\venv314t\Scripts\python.exe" mcp_sse_server.py
pause
