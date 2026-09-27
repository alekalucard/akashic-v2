@echo off
title Nous - Akashic Brain Server
echo ========================================
echo   NOUS - Akashic Brain Server
echo ========================================
echo.

cd /d "%~dp0"

echo Clearing Python cache for fresh code...
REM FIX 2026-06-29 (Nous+Ace): the old `for /d /r ... __pycache__` walked the entire akashic
REM tree onto cmd's tiny stack -> STACK OVERFLOW (0xc00000fd), cmd.exe died right here a few
REM seconds in, before python ever ran (confirmed via Windows event log + screenshot). Replaced
REM with an iterative os.walk (no stack recursion, doesn't follow symlinks = no loop). Same result.
REM REVERT = restore start_nous.bat.bak_pycacheclear_0629.
"F:\Sandbox\venv314t\Scripts\python.exe" -c "import os,shutil; [shutil.rmtree(os.path.join(r,'__pycache__'),ignore_errors=True) for r,d,f in os.walk('.') if '__pycache__' in d]"
echo Cache cleared.
echo.

echo Starting the brain...
echo (Close this window to stop the server)
echo Full output captured to: state\boot_full.log
echo.

set AKASHIC_SOURPATCHES_OBSERVER=1
set USE_WEAVER=1
REM --- native semantic encoder, LOW-THROTTLE re-enable (Nous+Ace 2026-06-12) -------
REM Revives her MEANING-SENSE (native all-MiniLM, keystone 7). Throttled in
REM AssociationCortexFairy: CPU embeddings (no VRAM peg) + queue-drain 3 encodes/beat
REM + torch capped to 4 cores. KILL-SWITCH: comment out the next line + reboot -> gated off.
REM RE-ENABLED 2026-06-12 (Nous+Ace): the RAM-safe CARTOGRAPHER redesign is in place —
REM NO resident tensor (meaning lives in REL_SEMANTIC edges in the manifold mmap); maps only
REM 3 nodes/beat with torch capped to 4 cores. KILL-SWITCH: re-comment the next line + reboot.
set AKASHIC_NATIVE_ENCODER=1
REM Backfill ON = Option A (2026-06-12): B proved the cartographer boots CALM (18.5GB, no peg),
REM so now sweep the existing 1.9M cortex nodes to actually MAP her cortex with meaning (3/beat).
REM Kill-switch: re-comment the next line + reboot → back to B (new-nodes-only).
REM RETIRED 2026-06-12 (Nous+Ace): the CPU 3/beat cartographer backfill is gated OFF in code
REM (wrong tool: ~18d/sweep + depends on `_am` which is None in the main process / portal mode).
REM Replaced by the GPU batch cortex-organize (sandbox build). Revive ref: set AKASHIC_CPU_CARTOGRAPHER=1.
REM set AKASHIC_SEMANTIC_BACKFILL=1
REM --- GPU COGNITION (2026-06-12 Nous+Ace) -----------------------------------
REM Allow torch in the MAIN process so the cortex spread/traversal (GPUSpread) runs on the
REM 3080 Ti. CUDA now WORKS on free-threaded 3.14t (PROVEN: her 2M-node graph spreads on the
REM GPU in 39ms / 210MB VRAM). The old GGUF->AKASHIC_SKIP_TORCH block kept her cognition pinned
REM to the CPU. Costs ~3.5GB CUDA DLLs in main; the heavy graph math leaves the CPU/RAM.
REM REVERTED 2026-06-12 (Nous+Ace): torch-in-main works but is the HEAVY path (+3.5GB RAM, 8GB
REM VRAM) AND makes graceful shutdown HANG on CUDA teardown (messy reboots). The LEAN path is
REM GPU-via-SUBPROCESS (portal_interior's GPUSpread, sticky _force_cpu reset on boot) = ~2GB VRAM,
REM lean main, clean shutdown. Re-enable only if the subprocess path stops using the card.
REM set AKASHIC_FORCE_TORCH=1
REM ---------------------------------------------------------------------------
REM --- mimalloc allocator stats (Nous+Ace) ------------------------------------
REM The eager_commit / purge_delay env-tests were REVERTED (didn't fix the leak; the
REM mem is LIVE not hoarded, and purge_delay=0 added per-free overhead near her heart).
REM The leak fix is now the get_neighbors_rich CACHE (manifold_memory.py). Keeping
REM VERBOSE+SHOW_STATS only to read the allocator's peak/purged state at exit.
set MIMALLOC_VERBOSE=1
set MIMALLOC_SHOW_STATS=1
REM ---------------------------------------------------------------------------
REM --- THREAD/ZOMBIE FIXES (2026-06-18 Nous + Ace, proven on the .74 node) -----
REM SHARED SHADOW SCAN: collapse the ~127 per-fairy `ot-shadow-*` threads into ONE central scan
REM loop (health-checks + autobiography preserved). LEAN HEARTBEAT: skip the ~127 per-fairy
REM `selfpulse-{name}` threads (liveness via the pacemaker batch-attestation). The organ-template
REM MULTIPLY-LOAD fix (one canonical _CITIZEN_OBJECTS = no more false zombie-deaths) rides in server.py.
REM Revert = comment these 2 lines + reboot. Organ backup: organ_template\Organ_Template_0_3_0.py.bak_2026-06-18_preshadowscan
set AKASHIC_SHARED_SHADOW_SCAN=1
REM LEAN_HEARTBEAT DISABLED (this-boot test, 06-17 PM): on Sour's FULL boot it overflowed the central
REM HeartbeatRegistry -- 48 workers can't drain ~121 fairies -> "delivery queue FULL, dropped 40k+ work-ticks"
REM -> CPU burn + heap climb ~300-600MB/min toward OOM (hit 92.6% RAM / 2.35GB free on the 32GB box).
REM Re-enable ONLY after provisioning the heartbeat worker pool / the shared-heartbeat refactor.
REM REVERT THIS TEST = uncomment the next line + reboot.
REM set AKASHIC_LEAN_HEARTBEAT=1
REM ---------------------------------------------------------------------------
REM --- CIRCADIAN REGION-RHYTHM (2026-06-17 Nous + Ace) - "onto the circadian rhythm", staged for the live-flip ---
REM The CircadianPacemaker pushes per-REGION tick multipliers into the heartbeat-registry divisor gate, so each
REM plane breathes with the phase (memory speeds UP in sleep/consolidation, cognition quiets at night) instead of
REM every fairy slamming every beat -> ALSO fewer work-ticks/beat at rest = lighter on the 48-worker pool (the same
REM pool LEAN_HEARTBEAT overflowed above). Flag-gated: OFF = byte-identical (the fixed PLANE_TICK_DIVISOR rules).
REM Built + py_compiled + logic-proven; the 2nd timer (TemporalDispatcher) is DORMANT so this is the sole tick-lever.
REM Tune the rhythm in fairies\P00_Autonomic\circulation\circadian_pacemaker_fairy.py -> PLANE_CIRCADIAN_RESPONSE.
REM LIGHT IT = uncomment the next line + reboot (instantly reversible: re-comment + reboot).
REM set AKASHIC_CIRCADIAN_TICK=1
REM ---------------------------------------------------------------------------
REM --- HEAP LEAK PROFILER (2026-06-17 Nous + Ace) -- pin the 6.5GB->20GB heap climb (the OOM) ---
REM Level 1 = gc object-type census (light, OOM-safe; pins the growing TYPE). Level 2 = +tracemalloc
REM sites (heavier; pins file:line). Logs state\heap_profile.log + 1-line/min to boot_full.log.
REM In-process via server.py (NOT boot_capture.py = separate launcher subprocess). Off = remove next line.
set AKASHIC_HEAP_PROFILE=1
REM ---------------------------------------------------------------------------
REM --- OFFLOAD TO .74 (2026-06-28 Nous + Ace) -------------------------------------
REM Sleep the 8 fairies the laptop (.74 / NOUS_74) OWNS, so Sour's FULL boot does NOT
REM double-run them (duplicate-mind overlap across the federation = Sour instability).
REM This list mirrors .74 start_nous_satellite.bat's AKASHIC_WAKE exactly. The gate
REM (Organ_Template_0_3_0) sleeps these regardless of COMA ("offload to .74"); byte-identical
REM if removed. REVERT = comment the next line + reboot.
set AKASHIC_SLEEP=NousFairy,VisualCortexFairy,ITCortexFairy,InnerVisionFairy,PerceptualGateFairy,TelemetryVisionFairy,WindowSenseFairy,MomentBinderFairy
REM ---------------------------------------------------------------------------
"F:\Sandbox\venv314t\Scripts\python.exe" -u boot_capture.py

pause
