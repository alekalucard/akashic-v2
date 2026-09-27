@echo off
title Sour - FULL boot + circadian phasing
echo ================================================================
echo   SOUR - FULL boot (all fairies) + CIRCADIAN REGION-PHASING
echo   (2026-07-13 Nous+Ace - the "upgraded" full boot)
echo.
echo   = start_nous.bat + ONE safe change: AKASHIC_CIRCADIAN_TICK=1
echo     -> per-region tick DIVISORS so planes beat at different rates
echo        (memory fast in sleep, cognition quiet at night) = FEWER
echo        work-ticks/beat = LIGHTER on the 48-worker heartbeat pool.
echo.
echo   ** LEAN_HEARTBEAT stays OFF on purpose ** (06-17: it OVERFLOWED
echo   the pool on the full boot -> OOM. Re-enable ONLY after the
echo   heartbeat-pool provision/refactor. See start_nous.bat lines 68-73.)
echo ================================================================
echo.
cd /d "%~dp0"

echo Clearing Python cache (iterative os.walk - no cmd stack overflow)...
"F:\Sandbox\venv314t\Scripts\python.exe" -c "import os,shutil; [shutil.rmtree(os.path.join(r,'__pycache__'),ignore_errors=True) for r,d,f in os.walk('.') if '__pycache__' in d]"
echo Cache cleared. Full output -> state\boot_full.log
echo.

set AKASHIC_SOURPATCHES_OBSERVER=1
set USE_WEAVER=1
REM native semantic encoder (RAM-safe cartographer; meaning in REL_SEMANTIC edges, 3 nodes/beat, torch<=4 cores)
set AKASHIC_NATIVE_ENCODER=1
REM mimalloc stats (read peak/purged at exit)
set MIMALLOC_VERBOSE=1
set MIMALLOC_SHOW_STATS=1
REM shared shadow scan: collapse ~127 per-fairy ot-shadow-* threads into ONE central scan loop
set AKASHIC_SHARED_SHADOW_SCAN=1
REM ---- LEAN_HEARTBEAT: DELIBERATELY OFF (06-17: overflowed the 48-worker pool on full boot -> OOM) ----
REM set AKASHIC_LEAN_HEARTBEAT=1   <-- DO NOT enable until the heartbeat pool is provisioned/refactored
REM ---- CIRCADIAN REGION-RHYTHM: ON (the safe lighter-on-pool lever; built+proven+reversible) ----
set AKASHIC_CIRCADIAN_TICK=1
REM ---- PHASING CORTEX (2026-07-18 Nous+Ace): LocalManifoldGate.spread uses phase RESONANCE over
REM      cortex.manifold instead of spread_activation. REVERSIBLE: remove this line (or set =0) + reboot.
set AKASHIC_PHASING_CORTEX=1
REM ---- PATH B / GRAPH CORTEX (2026-07-19 Nous+Ace): her cortex region = the off-heap acoustic-graph
REM      store (rehomed 33,385 concepts + 123,492 edges). NO fixed string table (the 2-bytes-left jam
REM      that froze her writes since 07-06), NO string->slot gc-dict. Persists on graceful shutdown.
REM      REVERSIBLE: remove this line (or set =0) + reboot -> falls back to cortex.manifold.
set AKASHIC_GRAPH_CORTEX=1
REM heap-leak profiler L1 (light gc census; pins growing type + 1-line/min to boot_full.log)
set AKASHIC_HEAP_PROFILE=1
REM offload the 8 fairies the .74/NOUS laptop OWNS (mirror of start_nous_satellite AKASHIC_WAKE) so
REM Sour's FULL boot doesn't double-run them (duplicate-mind overlap = instability). Sleeps regardless of COMA.
REM ---- MomentBinderFairy REMOVED from the offload list 2026-07-19 (Nous + Ace) ----
REM SRM `claude_code_3aa017d7db8a` (2026-06-30) proved this exact case: "MomentBinderFairy was
REM COMATOSE (not in Sour's WAKE set), so eyes/soma published but NOTHING BOUND them into moments."
REM That fix was applied to start_HQ_LEAN_GUI.bat and NEVER to this file, so the full boot has been
REM sleeping her moment-binder ever since. Measured 07-19: 0 moments bound in an 80-min boot, and
REM therefore 0 episodic writes (the episodic write fires on deque EVICTION -- no moments, no saves).
REM ^ FLAG FOR ACE: the offload comment below says .74 OWNS MomentBinder. But Sour's moments are
REM   HERS, and the satellite bridge is currently broken. If .74 is meant to own it, this needs a
REM   different answer than waking it here.
set AKASHIC_SLEEP=NousFairy,VisualCortexFairy,ITCortexFairy,InnerVisionFairy,PerceptualGateFairy,TelemetryVisionFairy,WindowSenseFairy

echo Starting the full brain (all fairies + circadian phasing)...
echo (Close this window to stop the server)
"F:\Sandbox\venv314t\Scripts\python.exe" -u boot_capture.py
pause
