@echo off
REM ==== Sour-as-HQ, LEAN LIVING slice (body-first Sour) — 2026-06-24 ====
REM COMA + plane-wake = wake the ENTIRE somatic plane (P20) + the cross-plane essentials.
REM Everything else stays comatose -> no 1.45M-cortex hammering, no 32GB OOM.
REM PRIMARY (no --satellite) -> PostalHTTPBridge on :8081.
REM coma/lean switch + UMF-consolidation fix + heartbeat-alive + the PLANE-WAKE gate are all in F:\.
cd /d F:\Sandbox\failure_factory\akashic_v2
set AKASHIC_COMA=1
REM --- wake the WHOLE somatic plane (Ace: "the entire somatic plan") via the plane-wake gate ---
set AKASHIC_WAKE_PLANES=P20
REM --- cross-plane essentials NOT in P20 (exact ACTOR_NAMEs): P10 memory, P30 manifold+cortex, P40 FF77-mesh ---
set AKASHIC_WAKE=SRMRecallFairy,SRMMemoryFairy,ManifoldConstrainedCortexFairy,AssociationCortexFairy,NeuralMeshFairy,VisualCortexFairy
REM --- defer within the somatic plane: sleep fairies + audio (headless) ---
set AKASHIC_SLEEP=DreamFairy,SleepWaveConductorFairy,HarmonicAffectBridgeFairy
REM --- heartbeat-alive (already wired in F:\): variable BPS + region-frequency ---
set AKASHIC_LEAN_HEARTBEAT=1
set AKASHIC_CIRCADIAN_TICK=1
REM --- COUNCIL (Nous->Sour port 2026-06-24): recall->USE deliberation over her clean core ---
set AKASHIC_SOUR_COUNCIL=1
REM --- lean shadow handling (mirror the proven node profile) ---
set AKASHIC_SHADOW_DEFER=1
set AKASHIC_SHARED_SHADOW_SCAN=1
REM --- HQ slice flags (from start_HQ_COMA.bat) ---
set AKASHIC_HEADLESS=1
set PYTHON_GIL=0
set AKASHIC_NODE=HQ_PC1
REM --- torch: make the REAL behaviour explicit (2026-08-27 Nous+Ace) ---
REM Her GGUF models exist, so server.py sets AKASHIC_SKIP_TORCH=1 and installs
REM _TorchBlocker. That blocker defines only find_module, REMOVED in Python 3.12,
REM so it never intercepts and torch loads regardless: measured 28 torch/CUDA maps,
REM 3.75 GB resident, and she holds a live CUDA context (1884 MiB, 14 pct util).
REM She has been running in FORCE_TORCH mode BY ACCIDENT. This makes it intentional:
REM GPU cognition stays ON and the log stops claiming a trap that cannot fire.
REM Behaviour is UNCHANGED by design -- this documents reality, it does not alter it.
REM REVERSIBLE: delete the set line below -> back to the (inert) trap.
set AKASHIC_FORCE_TORCH=1
REM --- network discovery: EXONERATED 2026-08-27 (Nous + Ace) ---
REM The 254-host ping sweep in network_explorer_fairy was the best-correlated
REM event with the empty-bytes singleton corruption, so it was gated off for a
REM single-variable A/B. Result: b'' DIED ANYWAY (edge just moved earlier, 40s
REM and 145 threads instead of 46-49s and 172). The sweep is NOT the trigger.
REM Restoring it. The gate stays in the code so the test can be repeated.
set AKASHIC_NETSCAN=1
set PY314T=F:\Sandbox\venv314t\Scripts\python.exe
echo [start_HQ_LEAN] COMA + WAKE_PLANES=P20 (whole somatic plane) + heartbeat-alive  -^> :8081, no OOM
echo   + cross-plane: SRM(recall+memory), Manifold+AssociationCortex, NeuralMesh ^| sleep: Dream/SleepWave/Harmonic
echo   CirculationPump(heart)+CircadianPacemaker auto-wake (P00/infra-exempt) = the circadian engine
"%PY314T%" -Xgil=0 -u server.py
