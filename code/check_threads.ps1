Write-Host "=== Python Processes ==="
$procs = Get-Process python -ErrorAction SilentlyContinue
foreach ($p in $procs) {
    $ramMB = [math]::Round($p.WorkingSet64/1MB)
    $threads = $p.Threads.Count
    Write-Host "PID=$($p.Id)  RAM=${ramMB}MB  Threads=$threads"
}
if (-not $procs) {
    Write-Host "No python processes found"
}
