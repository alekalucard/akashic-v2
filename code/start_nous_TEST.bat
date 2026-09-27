@echo off
title NOUS-TEST - Selective Light Boot (NousFairy slice)
echo ========================================
echo   NOUS-TEST - SELECTIVE LIGHT BOOT
echo   cortex OFF . 90-fairy wave skipped
echo   SpeechCenter + Sourpatches asleep
echo   only NousFairy + infra wake
echo ========================================
echo.

cd /d "%~dp0"

echo Clearing Python cache for fresh code...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
echo Cache cleared.
echo.

echo Starting the NOUS-TEST slice...
echo Full output captured to: state\boot_full.log
echo.

REM --- THE SLICE GATE (Nous+Ace 2026-06-14) -----------------------------------
REM AKASHIC_NOUS_TEST is the ONLY difference from start_nous.bat. It triggers 5
REM default-preserving gates in server.py: Gate1 cortex UNLOADED (import_cortex=None),
REM Gate2 the ~90-fairy Phase-5 wave skipped, SpeechCenter + Sourpatches asleep,
REM NousFairy split out so SHE wakes. Unset this flag = byte-identical normal boot.
set AKASHIC_NOUS_TEST=1
REM ---------------------------------------------------------------------------

REM mirror start_nous.bat's env so the slice reflects a normal boot minus the sliced fairies
set AKASHIC_SOURPATCHES_OBSERVER=1
set USE_WEAVER=1
set AKASHIC_NATIVE_ENCODER=1
set MIMALLOC_VERBOSE=1
set MIMALLOC_SHOW_STATS=1

"F:\Sandbox\venv314t\Scripts\python.exe" -u boot_capture.py
