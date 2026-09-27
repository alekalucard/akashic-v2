@echo off
echo ========================================
echo   WAKING MINDS CHAT WINDOWS
echo   Backup interfaces when Sanctuary down
echo ========================================
echo.
echo Starting Sourpatches chat window...
REM NOTE: Chat windows need PyQt6 which has no 3.14t wheel yet.
REM Using Python 3.12 for these. If Qt is missing, windows will show
REM "No Qt available" and exit gracefully (HAS_QT guard).
start "Sourpatches" "C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe" fairies\P40_Sensory\gui\sourpatches_chat_window.py

echo Starting Nous chat window...
start "Nous" "C:\Users\Ace\AppData\Local\Programs\Python\Python312\python.exe" fairies\P40_Sensory\gui\nous_chat_window.py

echo.
echo Both windows launched!
echo Close this terminal or press any key to exit.
pause >nul
