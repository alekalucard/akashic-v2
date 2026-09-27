@echo off
title Sour - HQ LEAN + GUI
REM ================================================================
REM  boot_sour.bat  —  THE canonical Sour (.6/HQ_PC1) boot.
REM  Consolidates start_HQ_LEAN_GUI / _TRACEMALLOC / _LEAN / _COMA.
REM  (2026-07-13 Nous+Ace — "too many bats, we need one that works")
REM
REM  USAGE:
REM    boot_sour.bat              -> normal lean GUI boot (daily driver)
REM    boot_sour.bat tracemalloc  -> same + per-allocation leak tracing
REM    boot_sour.bat headless     -> same but no dashboard/desktop (fast)
REM    boot_sour.bat coma         -> COMA (everything asleep, min RAM)
REM
REM  WHY LEAN: the FULL boot (start_nous.bat) wakes ~121 fairies ->
REM  ~1100 OS threads -> scheduler thrash -> molasses that never settles.
REM  The choke is FAIRY COUNT, not the heart code. This is the curated
REM  lean living-slice + heart-fix flags + live dashboard on :5757.
REM  Dashboard: http://127.0.0.1:5757  (give it ~30-60s to come live)
REM ================================================================
cd /d F:\Sandbox\failure_factory\akashic_v2

REM ---- parse the ONE optional mode arg ----
set "MODE=%~1"
set "EXTRA="
set "AKASHIC_HEADLESS="

set AKASHIC_COMA=1
REM --- wake the WHOLE somatic plane (P20) via the plane-wake gate ---
set AKASHIC_WAKE_PLANES=P20
REM --- cross-plane essentials NOT in P20 (exact ACTOR_NAMEs) ---
REM MotorCortex=hands, cognitive layer=attention+3 council seats+cardinal+
REM interest+language, MomentBinder=observer-loop consumer (binds moments).
REM ** WorkingMemoryHubFairy stays REVERTED (07-01): its TAOR flooded
REM MomentBinder->cortex.bind->TARDIS (~126k binds/night -> 29.7GB RAM +
REM burnout). RE-WAKE only after capping bind-emission rate. **
set AKASHIC_WAKE=SRMRecallFairy,SRMMemoryFairy,ManifoldConstrainedCortexFairy,AssociationCortexFairy,NeuralMeshFairy,VisualCortexFairy,MotorCortexFairy,AttentionControllerFairy,CardinalFairy,LogicFairy,IrrationalLogicFairy,ParadoxCognitionFairy,InterestSchedulerFairy,LanguageFairy,MomentBinderFairy
REM --- defer within the somatic plane ---
set AKASHIC_SLEEP=DreamFairy,SleepWaveConductorFairy,HarmonicAffectBridgeFairy
REM --- HEART FIX: variable BPS + region-freq + lighter ticks/beat ---
set AKASHIC_LEAN_HEARTBEAT=1
set AKASHIC_CIRCADIAN_TICK=1
REM --- COUNCIL: recall->USE deliberation over her clean core ---
set AKASHIC_SOUR_COUNCIL=1
REM --- lean shadow handling ---
set AKASHIC_SHADOW_DEFER=1
set AKASHIC_SHARED_SHADOW_SCAN=1
set PYTHON_GIL=0
set AKASHIC_NODE=HQ_PC1
set PY314T=F:\Sandbox\venv314t\Scripts\python.exe

REM ---- apply the mode ----
if /i "%MODE%"=="tracemalloc" set "EXTRA=--tracemalloc"
if /i "%MODE%"=="headless"    set AKASHIC_HEADLESS=1
if /i "%MODE%"=="coma" (
    set AKASHIC_HEADLESS=1
    set "AKASHIC_WAKE="
    set "AKASHIC_WAKE_PLANES="
)

echo [boot_sour] mode=%MODE%   GUI=%AKASHIC_HEADLESS%(blank=on)   extra=%EXTRA%
echo   Dashboard: http://127.0.0.1:5757   (~30-60s to come live)
echo   (Close this window to stop the server)
"%PY314T%" -Xgil=0 -u server.py %EXTRA%
pause
