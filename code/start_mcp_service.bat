@echo off
title Akashic MCP Service
cd /d "F:\Sandbox\failure_factory\akashic_v2"
echo Starting Akashic MCP Service...
echo.
echo Claude Code should connect to: http://127.0.0.1:8765/sse
echo.
"F:\Sandbox\venv314t\Scripts\python.exe" mcp_service.py run
pause
