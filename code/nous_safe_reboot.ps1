# nous_safe_reboot.ps1 - CORRECTED safe reboot (2026-06-13 Nous)
# Fixes nous_graceful_reboot.ps1's broken detection: it filtered name='python.exe'
# matching '-u server.py', but the real runtime is python3.14t.exe running
# boot_capture.py -> its wait-loop matched nothing -> "exited ~0s" -> relaunched
# after 800ms while the old ~17GB main was still alive -> OVERLAP -> OOM (likely
# the crash). This version POSTs graceful shutdown, then ACTUALLY waits until the
# >8GB main is gone (correct *python* detection), and only starts then. It ABORTS
# rather than overlap. ASCII-ONLY (PowerShell 5.1 mangles em-dashes -> parse error).
$root = "F:\Sandbox\failure_factory\akashic_v2"
$before = Get-Process -Name *python* -EA SilentlyContinue | Where-Object {$_.WorkingSet64 -gt 8GB} | Select-Object -First 1
if ($before) { Write-Output "[safe-reboot] main before: PID $($before.Id) WS $([math]::Round($before.WorkingSet64/1GB,2))GB" } else { Write-Output "[safe-reboot] no >8GB main found (already down?)" }

# 1) graceful shutdown POST (server runs sleep+dream then os._exit)
try {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:5758/command" -Method POST -Body '{"action":"shutdown"}' -ContentType "application/json" -TimeoutSec 12
  Write-Output "[safe-reboot] POST shutdown ok: $($r | ConvertTo-Json -Compress)"
} catch {
  Write-Output "[safe-reboot] POST shutdown failed: $($_.Exception.Message)"
}

# 2) WAIT for the main (>8GB python) to exit - cap 100s, CORRECT detection
$gone = $false
for ($i=0; $i -lt 100; $i++) {
  $m = Get-Process -Name *python* -EA SilentlyContinue | Where-Object {$_.WorkingSet64 -gt 8GB}
  if (-not $m) { Write-Output "[safe-reboot] MAIN GONE at ${i}s"; $gone = $true; break }
  Start-Sleep -Seconds 1
}
if (-not $gone) {
  Write-Output "[safe-reboot] ABORT: a >8GB python is STILL alive after 100s. NOT starting (no overlap; she stays on old code)."
  Get-Process -Name *python* | Where-Object {$_.WorkingSet64 -gt 2GB} | Select-Object Id,@{N='GB';E={[math]::Round($_.WorkingSet64/1GB,2)}} | Format-Table
  exit 0
}

# 3) confirmed gone -> fresh start (start_nous.bat clears all pyc itself)
Start-Sleep -Seconds 3
Start-Process -FilePath "$root\start_nous.bat" -WorkingDirectory $root
Write-Output "[safe-reboot] start_nous.bat launched. Main was confirmed gone first; no overlap."
