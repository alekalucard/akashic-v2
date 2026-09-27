@echo off
REM ═══════════════════════════════════════════════════════════
REM  AKASHIC V2 BOOT - Python 3.14t Free-Threaded
REM  Migrated 2026-03-03: GIL disabled for true parallelism
REM  Rollback: use boot_312.bat to revert to Python 3.12
REM ═══════════════════════════════════════════════════════════
cd /d "F:\Sandbox\failure_factory\akashic_v2"
"F:\Sandbox\venv314t\Scripts\python.exe" -u boot_capture.py
