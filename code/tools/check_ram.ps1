$os = Get-CimInstance Win32_OperatingSystem
$totalGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$freeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$usedGB = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1)
Write-Host "RAM: ${usedGB}GB used / ${totalGB}GB total (${freeGB}GB free)"
Write-Host ""
Write-Host "Top 15 processes by RAM:"
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 15 | ForEach-Object {
    $mb = [math]::Round($_.WorkingSet64 / 1MB)
    Write-Host ("{0,-30} PID={1,-8} {2}MB" -f $_.ProcessName, $_.Id, $mb)
}
