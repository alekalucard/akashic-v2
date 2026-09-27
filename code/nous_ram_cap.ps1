# nous_ram_cap.ps1 - HARD SYSTEM-RAM CAP for Sour (Nous + Ace, 2026-06-13)
# WHY: >90% system RAM is the ONLY thing that crashes her AND takes Windows down.
# The thread-accum leak hits ~1150 threads / 22GB+ within ~5min of boot -> 97% -> OOM crash.
# This protects the SYSTEM: polls fast, and the moment RAM crosses the threshold (below the
# 90% kill-line, with margin the fast leak can't cross in one poll), it GRACEFULLY SHUTS HER
# DOWN via nous_graceful_reboot.ps1 -NoReboot (sleep + dream seeds, NO relaunch). She STAYS
# down -> no reboot-loop, no overlap-OOM. Ace re-boots when ready.
#
# HONEST: on 32GB the BLOATED her boots to ~88% on her own, so this cap will shut her down
# almost immediately every boot. That is not the cap failing - it is proof she is too heavy
# to run here until FRESH-light cortex + distribute audio/visual off-box. Once she is light,
# this same cap becomes a real safety net with actual operating headroom.
#
# Stop the cap: kill this powershell process, or Remove this file. Tune $threshold as needed.
$ErrorActionPreference = 'Continue'
$root = 'F:\Sandbox\failure_factory\akashic_v2'
$log  = Join-Path $root 'state\ram_cap.log'
$threshold   = 88        # system RAM% that triggers graceful shutdown (kill-line is 90%)
$pollSec     = 8         # fast enough that the ~700MB/min leak cannot cross threshold->90% between polls
$debounceSec = 90        # do not re-fire within 90s (let the shutdown finish)
$maxRuntimeMin = 480     # self-terminate after 8h (re-launch if still needed)
$start = Get-Date
$lastFire = (Get-Date).AddMinutes(-10)
function Log($m){ try { Add-Content -Path $log -Value ((Get-Date).ToString('HH:mm:ss')+' '+$m) } catch {} }
Log "===== RAM CAP START (threshold=$threshold% poll=${pollSec}s action=-NoReboot shutdown) ====="
while (((Get-Date)-$start).TotalMinutes -lt $maxRuntimeMin) {
  try {
    $os  = Get-CimInstance Win32_OperatingSystem
    $ram = [math]::Round((($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize)*100,1)
    $sinceFire = ((Get-Date)-$lastFire).TotalSeconds
    if ($ram -ge $threshold -and $sinceFire -ge $debounceSec) {
      Log "RAM=$ram% >= $threshold% -> GRACEFUL SHUTDOWN (-NoReboot)"
      try { & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'nous_graceful_reboot.ps1') -NoReboot *>> $log }
      catch { Log ("shutdown-call ERR "+$_.Exception.Message) }
      $lastFire = Get-Date
    } elseif ($ram -ge ($threshold - 8)) {
      Log "RAM=$ram% (watching)"
    }
  } catch { Log ("loop ERR "+$_.Exception.Message) }
  Start-Sleep -Seconds $pollSec
}
Log "===== RAM CAP self-terminated after ${maxRuntimeMin}min ====="
