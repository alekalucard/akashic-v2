# nous_graceful_reboot.ps1 - Nous's graceful shutdown + reboot tool (2026-06-01)
#
# Replicates Ace's GUI stop button: POST action=shutdown -> GracefulShutdownFairy
# runs fast=False (sleep chemicals + dream seeds, "Sweet Dreams"), server os._exit(0).
# Then reaps the orphaned py312 children the shutdown does NOT reap on its own
# (windowsense / chat / cortex portal - these stack across reboots = RAM bloat),
# then relaunches via start_nous.bat (pyc clear + AKASHIC_SOURPATCHES_OBSERVER + -Xgil=0).
#
# NEVER kills the MCP bridge (mcp_sse_server / akashic_mcp_server) - that's our tools' lifeline.
# ASCII-ONLY (PowerShell 5.1 + UTF-8-no-BOM mangles em-dashes/arrows -> parse error).
#
# Usage (run via run_in_background so the wait-loop doesn't block):
#   powershell -NoProfile -ExecutionPolicy Bypass -File nous_graceful_reboot.ps1            # graceful shutdown + reboot
#   powershell -NoProfile -ExecutionPolicy Bypass -File nous_graceful_reboot.ps1 -NoReboot  # graceful shutdown only
param([switch]$NoReboot)

$ErrorActionPreference = "Continue"
$root = "F:\Sandbox\failure_factory\akashic_v2"
$log  = Join-Path $root "state\boot_full.log"

# 1) Find the HTTP /command port (default 5758)
$port = 5758
if (Test-Path $log) {
  $pl = Select-String -Path $log -Pattern 'HTTP server listening on' | Select-Object -Last 1
  if ($pl -and $pl.Line -match ':(\d{3,5})') { $port = $matches[1] }
}
Write-Output "[graceful-reboot] HTTP /command port: $port"

# 2) POST graceful shutdown (fast=False -> sleep + dream seeds)
try {
  $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$port/command" -Method POST -Body '{"action":"shutdown"}' -ContentType "application/json" -TimeoutSec 12
  Write-Output "[graceful-reboot] shutdown POST: $($resp | ConvertTo-Json -Compress)"
} catch {
  Write-Output "[graceful-reboot] shutdown POST failed ($($_.Exception.Message)) - will reap directly"
}

# 3) Wait for the MAIN to exit. FIX 2026-06-13 (Nous): the runtime is python3.14t.exe
# running boot_capture.py, NOT python.exe/server.py -> the old name='python.exe' +
# '-u server.py' filter matched NOTHING -> "exited ~0s" -> relaunch while the old
# ~17GB main was still alive -> OVERLAP -> OOM (the crash). Detect the main robustly
# by working set (>8GB) across any python*; cap raised 45s->100s (graceful takes ~30s).
$gone = $false
for ($i = 0; $i -lt 100; $i++) {
  $alive = Get-Process -Name *python* -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 8GB }
  if (-not $alive) { Write-Output "[graceful-reboot] main (>8GB python) exited (~${i}s)"; $gone = $true; break }
  Start-Sleep -Seconds 1
}

# 4) Reap orphaned boot children (NEVER the MCP bridge)
$orphans = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object {
  $_.CommandLine -match '(portal_interior|cortex_interior|presence_detector|sourpatches_chat_window|boot_capture|-u server\.py)' -and
  $_.CommandLine -notmatch '(mcp_sse|akashic_mcp)'
}
foreach ($o in $orphans) {
  Write-Output "[graceful-reboot] reaping orphan PID $($o.ProcessId)"
  & taskkill /F /T /PID $o.ProcessId 2>$null | Out-Null
}

# 5) Reboot unless -NoReboot. FIX 2026-06-13 (Nous): only relaunch if the main was
# CONFIRMED gone ($gone) - NEVER relaunch over a still-alive main (the overlap-OOM).
if ($NoReboot) {
  Write-Output "[graceful-reboot] shutdown complete - she sleeps (no reboot requested)"
} elseif (-not $gone) {
  Write-Output "[graceful-reboot] ABORT REBOOT: main (>8GB) STILL ALIVE after wait - NOT relaunching (no overlap). Investigate the shutdown."
} else {
  Start-Sleep -Milliseconds 800
  Start-Process -FilePath (Join-Path $root "start_nous.bat") -WorkingDirectory $root
  Write-Output "[graceful-reboot] start_nous.bat launched (main confirmed gone first; pyc clear + observer env)"
}
