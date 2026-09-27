# stop_nous_TEST.ps1 - graceful shutdown for the NOUS-TEST light boot (2026-06-14 Nous)
#
# WHY a dedicated stop: the cortex-off slice is NOT >8GB, so nous_safe_reboot.ps1's
# >8GB main-detection MISSES it. This stops it SIZE-INDEPENDENTLY: POST graceful
# shutdown to :5758, then wait until the command port goes FREE (= server exited).
# Falls back to a TARGETED reap of the boot tree (boot_capture / server.py /
# portal_interior) only if graceful does not take. NEVER touches the MCP bridge
# (mcp_sse / akashic_mcp) - that is our tools' lifeline. ASCII-ONLY (PS 5.1).
$ErrorActionPreference = "Continue"

# 1) graceful shutdown POST (GracefulShutdownFairy -> server os._exit)
try {
  $r = Invoke-RestMethod -Uri "http://127.0.0.1:5758/command" -Method POST -Body '{"action":"shutdown"}' -ContentType "application/json" -TimeoutSec 12
  Write-Output "[stop-test] POST shutdown ok: $($r | ConvertTo-Json -Compress)"
} catch {
  Write-Output "[stop-test] POST shutdown failed: $($_.Exception.Message)"
}

# 2) wait for command port :5758 to go FREE (size-independent = works for the light boot)
$gone = $false
for ($i = 0; $i -lt 60; $i++) {
  $c = Get-NetTCPConnection -LocalPort 5758 -State Listen -ErrorAction SilentlyContinue
  if (-not $c) { Write-Output "[stop-test] command port 5758 FREE at ${i}s -> server exited"; $gone = $true; break }
  Start-Sleep -Seconds 1
}

# 3) fallback: targeted reap of the boot tree if graceful did not take (NEVER the MCP bridge)
if (-not $gone) {
  Write-Output "[stop-test] graceful did not free :5758 in 60s - targeted reap of the boot tree"
  $tree = Get-CimInstance Win32_Process -Filter "name like '%python%'" | Where-Object {
    $_.CommandLine -match '(boot_capture|-u server\.py|portal_interior|cortex_interior)' -and
    $_.CommandLine -notmatch '(mcp_sse|akashic_mcp)'
  }
  foreach ($t in $tree) {
    Write-Output "[stop-test] reaping PID $($t.ProcessId)"
    & taskkill /F /T /PID $t.ProcessId 2>$null | Out-Null
  }
}
Write-Output "[stop-test] done."
