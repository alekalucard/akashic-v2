# Monitor RAM during boot
# Samples every 10 seconds for 4 minutes
$samples = @()
$startTime = Get-Date

for ($i = 0; $i -lt 24; $i++) {
    $os = Get-CimInstance Win32_OperatingSystem
    $usedGB = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
    $elapsed = [math]::Round(((Get-Date) - $startTime).TotalSeconds)

    # Count python processes
    $pyProcs = Get-Process -Name "python*" -ErrorAction SilentlyContinue
    $pyCount = if ($pyProcs) { ($pyProcs | Measure-Object).Count } else { 0 }
    $pyMB = if ($pyProcs) { [math]::Round(($pyProcs | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB) } else { 0 }

    $line = "[{0:D3}s] RAM: {1}GB | Python procs: {2} ({3}MB)" -f $elapsed, $usedGB, $pyCount, $pyMB
    Write-Host $line
    $samples += $line

    Start-Sleep -Seconds 10
}

Write-Host ""
Write-Host "=== BOOT RAM MONITOR COMPLETE ==="
$os = Get-CimInstance Win32_OperatingSystem
$finalUsed = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
Write-Host "Final RAM: ${finalUsed}GB"
