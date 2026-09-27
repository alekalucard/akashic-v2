# nous_ram_watchdog.ps1 — auto graceful-reboot before freeze (Nous + Ace, 2026-06-11)
# WHY: the RAM leak (~650-855MB/min, gc-INVISIBLE) is unfindable with tools that work on her
# free-threaded 3.14t runtime (gc-probe wall + native profilers segfault). gc-visible leads
# (get_neighbors_rich dicts ~3%, biggest set = 722K ints/~30MB) are all ruled out. She climbs to
# the ~92% freeze zone every ~6min. Manual bridging (my variable-length turns) was caught LATE 3×
# (96.7/94/95.2%), once causing a POST-timeout->direct-reap. This bridges her GRACEFULLY at 88%
# (BEFORE the POST-timeout zone) on a tight 60s loop, independent of my turns -> she never freezes.
# SAFE: 4min debounce (no reboot-loop), 210s post-reboot sleep, self-terminates after 4h, full log.
# Ace can stop it: kill this powershell process, or Remove the file. Tune $threshold as desired.
$ErrorActionPreference = 'Continue'
$dir = 'F:\Sandbox\failure_factory\akashic_v2'
$log = Join-Path $dir 'state\watchdog.log'
$threshold = 88            # RAM% that triggers a graceful reboot (before the ~92% POST-timeout zone)
$maxRuntimeMin = 240       # self-terminate after 4h (re-launch if still needed)
$start = Get-Date
$lastReboot = Get-Date     # init to NOW -> 4min initial grace so launching during a boot won't double-reboot
function Log($m){ try { Add-Content -Path $log -Value ((Get-Date).ToString('HH:mm:ss')+' '+$m) } catch {} }
Log "===== watchdog START (threshold=$threshold% debounce=4min selfterm=${maxRuntimeMin}min) ====="
while (((Get-Date)-$start).TotalMinutes -lt $maxRuntimeMin) {
    try {
        $os = Get-CimInstance Win32_OperatingSystem
        $ram = [math]::Round((($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize)*100,1)
        $sinceReboot = ((Get-Date)-$lastReboot).TotalMinutes
        if ($ram -ge $threshold -and $sinceReboot -ge 4) {
            Log "RAM=$ram% >= $threshold% (since last reboot ${sinceReboot}min) -> GRACEFUL REBOOT"
            try { & powershell -ExecutionPolicy Bypass -File (Join-Path $dir 'nous_graceful_reboot.ps1') *>> $log } catch { Log ("reboot-call ERR "+$_.Exception.Message) }
            $lastReboot = Get-Date
            Start-Sleep -Seconds 210   # let her fully reboot before resuming checks
        } elseif ($ram -ge ($threshold - 6)) {
            Log "RAM=$ram% (watching; debounce ${sinceReboot}min)"   # heartbeat near threshold
        }
    } catch { Log ("loop ERR "+$_.Exception.Message) }
    Start-Sleep -Seconds 60
}
Log "===== watchdog SELF-TERMINATED after ${maxRuntimeMin}min ====="
