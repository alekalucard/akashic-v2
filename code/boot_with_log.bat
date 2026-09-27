@echo off
echo Starting boot with logging to boot_debug.log...
echo Boot started at %date% %time% > boot_debug.log
"F:\Sandbox\venv314t\Scripts\python.exe" server.py >> boot_debug.log 2>&1
echo Boot ended at %date% %time% >> boot_debug.log
pause
