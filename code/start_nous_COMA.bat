@echo off
title NOUS-COMA - chemically-induced coma boot (orderly system)
echo ========================================
echo   NOUS-COMA BOOT
echo   AKASHIC_COMA=1 : every fairy registers but stays ASLEEP (on_boot skipped)
echo   AKASHIC_WAKE   : "%AKASHIC_WAKE%"  (these wake; their on_boot runs)
echo   postal hub + MCP server stay up
echo ========================================
echo.

cd /d "%~dp0"

echo Clearing Python cache for fresh code...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
echo Cache cleared.
echo.

REM --- THE COMA SWITCH (Nous+Ace 2026-06-14) -----------------------------------
REM AKASHIC_COMA=1 -> every fairy boots registered-but-inert (on_boot SKIPPED) via the
REM organ-template gate, immune to which boot path woke it. AKASHIC_WAKE (inherited from
REM the parent shell) names the fairies to wake. No AKASHIC_COMA = byte-identical normal boot.
set AKASHIC_COMA=1
REM ---------------------------------------------------------------------------

REM mirror start_nous.bat env (NOT AKASHIC_NOUS_TEST — the coma switch supersedes the slice gates)
set AKASHIC_SOURPATCHES_OBSERVER=1
set USE_WEAVER=1
set AKASHIC_NATIVE_ENCODER=1
set MIMALLOC_VERBOSE=1
set MIMALLOC_SHOW_STATS=1

"F:\Sandbox\venv314t\Scripts\python.exe" -u boot_capture.py
