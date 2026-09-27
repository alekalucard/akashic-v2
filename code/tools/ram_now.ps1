$os = Get-CimInstance Win32_OperatingSystem
$used = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
$free = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
Write-Host "RAM: ${used}GB used, ${free}GB free"

$pyProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue
if ($pyProcs) {
    $count = ($pyProcs | Measure-Object).Count
    $totalMB = [math]::Round(($pyProcs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB)
    Write-Host "Python processes: $count (total ${totalMB}MB)"
    $pyProcs | Sort-Object WorkingSet64 -Descending | ForEach-Object {
        $mb = [math]::Round($_.WorkingSet64 / 1MB)
        $cmd = $_.Path
        if ($cmd.Length -gt 60) { $cmd = $cmd.Substring(0,60) + "..." }
        Write-Host ("  PID={0,-8} {1}MB  {2}" -f $_.Id, $mb, $cmd)
    }
} else {
    Write-Host "No Python processes"
}
