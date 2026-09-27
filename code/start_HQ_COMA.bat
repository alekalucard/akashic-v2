@echo off
REM ==== Sour-as-HQ, lean coma-slice (postal HEADQUARTERS for the bridge) ====
REM COMA: only P00 autonomic + infra wake -> no cortex load, no 32GB OOM.
REM PRIMARY (no --satellite) -> server.py starts the PostalHTTPBridge on :8081.
REM HEADLESS: skip the GUI status-refresh (this is a bridge-test slice).
cd /d F:\Sandbox\failure_factory\akashic_v2
set AKASHIC_COMA=1
set AKASHIC_HEADLESS=1
set PYTHON_GIL=0
set AKASHIC_NODE=HQ_PC1
set PY314T=F:\Sandbox\venv314t\Scripts\python.exe
echo [start_HQ] COMA=1 HEADLESS=1 PRIMARY  -^> :8081 receiver, no OOM
"%PY314T%" -Xgil=0 -u server.py
