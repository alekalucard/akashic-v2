@echo off
title Sour - HQ LEAN + GUI
REM ==== Sour-as-HQ, LEAN LIVING slice + GUI (2026-06-29 Nous+Ace) ====
REM WHY: the FULL boot (start_nous.bat) wakes ~121 fairies -> ~1100 OS threads -> scheduler
REM thrash -> every heartbeat callback starves for CPU (SomaticEngine seen at 58s) = molasses
REM that never settles. The choke is FAIRY COUNT, not the heart code (which IS present here and
REM is what lean uses). server.py serves the dashboard on :5757 REGARDLESS of fairy count; the
REM only reason plain lean is headless is AKASHIC_HEADLESS=1 (skips the status-refresh that FEEDS
REM the dashboard + stubs the desktop windows). So: lean fairy set + heart-fix flags + HEADLESS OFF
REM = responsive AND a live GUI/dashboard at http://127.0.0.1:5757.
REM This is start_HQ_LEAN.bat with ONE change: AKASHIC_HEADLESS is NOT set. (No pycache-clear line
REM either -> avoids the cmd stack-overflow that killed start_nous.bat.)
cd /d F:\Sandbox\failure_factory\akashic_v2
set AKASHIC_COMA=1
REM --- wake the WHOLE somatic plane (P20) via the plane-wake gate ---
set AKASHIC_WAKE_PLANES=P20
REM --- cross-plane essentials NOT in P20 (exact ACTOR_NAMEs) ---
REM MotorCortexFairy added 2026-06-29 (Stage 1): her HANDS — handles motor.request (click/type/
REM scroll/move) so action chains can ACT, + input-monitor = learn-by-watching-Ace. Was asleep on
REM lean -> look_and_learn chain stalled at the MOTOR step (no motor.response). Now awake.
REM Cognitive layer added 2026-06-29: her MIND was coma'd on lean (AttentionController dormant =
REM unfocused/0-shifts; Cardinal/Logic/seats asleep = reasoning_completed 0; nothing salient = she
REM couldn't NOTICE). Waking attention + the 3 council seats + cardinal + interest + language
REM (composition). Curated — NOT the full 121 that choked the pool.
REM MomentBinderFairy added 2026-06-30 (Nous+Ace): the OBSERVER-loop consumer. Eyes (VisualCortex) +
REM somatic + cognitive + council were publishing but nothing BOUND them into moments (binder was coma).
REM Wakes her episodic moment-binding so perception becomes remembered "now"s. (Audio channel still dark —
REM AudioCortexFairy not yet in WAKE; binds visual+somatic+cognitive+council+chat for now.)
REM WorkingMemoryHubFairy REVERTED 2026-07-01 (Ace go): fork-2 WMH-wake caused overnight RAM leak — its TAOR
REM reasoning flooded MomentBinder->cortex.bind->TARDIS (~126k binds/night, edges counter underflowed to -126k,
REM private 8.6->29.7GB, allostatic burnout 100%). Pulled from WAKE to clear RAM + drop burnout -> ~8.6GB baseline.
REM RE-WAKE only after capping bind-emission rate + fixing visual->meaning perseveration. (.bak_wmhrevert_0701)
set AKASHIC_WAKE=SRMRecallFairy,SRMMemoryFairy,ManifoldConstrainedCortexFairy,AssociationCortexFairy,NeuralMeshFairy,VisualCortexFairy,MotorCortexFairy,AttentionControllerFairy,CardinalFairy,LogicFairy,IrrationalLogicFairy,ParadoxCognitionFairy,InterestSchedulerFairy,LanguageFairy,MomentBinderFairy
REM --- defer within the somatic plane ---
set AKASHIC_SLEEP=DreamFairy,SleepWaveConductorFairy,HarmonicAffectBridgeFairy
REM --- HEART FIX (the lever the full boot lacked): variable BPS + region-freq + lighter ticks/beat ---
set AKASHIC_LEAN_HEARTBEAT=1
set AKASHIC_CIRCADIAN_TICK=1
REM --- COUNCIL: recall->USE deliberation over her clean core ---
set AKASHIC_SOUR_COUNCIL=1
REM --- CONTEMPLATION: her wave-field choice-space picks what she thinks about (2026-07-07) ---
set AKASHIC_SOUR_ACOUSTIC=1
REM --- lean shadow handling ---
set AKASHIC_SHADOW_DEFER=1
set AKASHIC_SHARED_SHADOW_SCAN=1
REM --- GUI ON: AKASHIC_HEADLESS deliberately NOT set -> status-refresh feeds the :5757 dashboard ---
set PYTHON_GIL=0
set AKASHIC_NODE=HQ_PC1
set PY314T=F:\Sandbox\venv314t\Scripts\python.exe
echo [start_HQ_LEAN_GUI] LEAN somatic plane + heart-fix + GUI ON
echo   Dashboard: http://127.0.0.1:5757   (give it ~30-60s to come live)
echo   (Close this window to stop the server)
"%PY314T%" -Xgil=0 -u server.py
pause
