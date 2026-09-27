' Akashic MCP SSE Server - Hidden Startup Launcher
' Place this in: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
' Or copy start_mcp_server.bat there directly if you prefer seeing the window.

Set oShell = CreateObject("WScript.Shell")
oShell.CurrentDirectory = "F:\Sandbox\failure_factory\akashic_v2"
oShell.Run "cmd /c start_mcp_server.bat", 0, False
