@echo off
REM ============================================================
REM  .74 SATELLITE LAUNCHER  (boot LOCALLY on .74, OR remote-launch from PC1)
REM  Mirrors start_nous.bat's flow (boot_capture.py wrapper) but as the lean
REM  Nous slice: Sour's cortex stays dark, NousFairy wakes, and the node
REM  forwards consciousness home to PC1 (HQ) at 192.168.1.6:8081.
REM  Do NOT run this on PC1 -- it would try to satellite to itself.
REM ============================================================
title Nous Satellite (.74) -^> PC1 HQ 192.168.1.6:8081

cd /d "%~dp0"

echo Clearing Python cache for fresh code...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
echo Cache cleared.
echo.

REM --- Satellite slice: lean Nous awake, Sour cortex dark, headless, forward home ---
set AKASHIC_COMA=1
REM Lean heartbeat (2026-06-17 proof, Ace go'd): skip per-fairy selfpulse threads;
REM liveness via the pacemaker's central batch-attestation. Revert = delete these 3 lines.
set AKASHIC_LEAN_HEARTBEAT=1
REM AUTO-ROUTER (2026-06-17): bind the postal tunnel to 0.0.0.0 so PC1's MCP can fail over to this node when PC1's down.
set AKASHIC_TUNNEL_LAN=1
REM SHADOW DEFER (2026-06-18 Nous + Ace, proving on the node): comatose fairies skip their per-fairy
REM `ot-shadow-*` thread (~94 -> ~7). The central blueprint_watcher (Layer 2) covers source-watch + hot-reload;
REM liveness is the registry pulse, not the shadow. Revert = delete these 3 lines. Default-preserving when unset.
set AKASHIC_SHADOW_DEFER=1
REM SHARED SHADOW SCAN (2026-06-18 Nous + Ace, proving on the node): SUPERSEDES shadow-defer — ALL fairies'
REM per-fairy `ot-shadow-*` thread -> ONE central `shared-shadow-scan` loop (ot:40 -> ~0). Comatose skip entirely;
REM awake register with the central scan (health-checks + autobiography preserved). Revert = delete these 3 lines.
set AKASHIC_SHARED_SHADOW_SCAN=1
REM Nous + the VISUAL CORTEX live here now (moved off PC1 2026-06-15, Ace's call).
REM PARADOX CLUSTER woken 2026-07-05 (Ace's call): the emotional-superposition substrate
REM + paradox-thinking path were booting COMATOSE (on_boot skipped) -> the paradox fix never ran
REM in live cognition. Waking QuantumEmulator (superposition/decay loop + quantum_state.json dump),
REM ParadoxCognition, IrrationalLogic, QuantumInterference. Revert = remove the 4 trailing names.
set AKASHIC_WAKE=NousFairy,VisualCortexFairy,ITCortexFairy,InnerVisionFairy,PerceptualGateFairy,TelemetryVisionFairy,WindowSenseFairy,QuantumEmulatorFairy,ParadoxCognitionFairy,IrrationalLogicFairy,QuantumInterferenceFairy
set AKASHIC_HEADLESS=1
set AKASHIC_NODE=NOUS_74
REM GPU ENABLED 2026-06-15: .74 now has auto-login + a desktop session, and the
REM visual cortex moved here -> it needs the 3070 (Florence/ITCortex). SKIP_TORCH off.
REM (re-add "set AKASHIC_SKIP_TORCH=1" to force CPU-only if the GPU path misbehaves.)
set PYTHON_GIL=0
set MIMALLOC_VERBOSE=1
set MIMALLOC_SHOW_STATS=1
REM .74 has no venv314t -> base python3.14t (proven there); boot_capture auto-detects + adds -Xgil=0
set PY314T=%LOCALAPPDATA%\Programs\Python\Python314\python3.14t.exe

echo Starting Nous satellite via boot_capture (--satellite --primary-ip 192.168.1.6)...
echo Full output -^> state\boot_full.log
echo.

REM Idempotency guard: don't double-boot if a satellite is already up on :5758
REM (lets the logon-task fire safely even if one's already running).
netstat -ano | findstr ":5758" | findstr /i "LISTENING" >nul 2>&1
if not errorlevel 1 (
  echo [guard] Satellite already running on :5758 -- skipping duplicate launch.
  goto :eof
)

"%PY314T%" -u boot_capture.py --satellite --primary-ip 192.168.1.6
REM (no pause: suited for remote launch / auto-start; server runs until shutdown)
