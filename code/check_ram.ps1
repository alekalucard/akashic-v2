Write-Host "=== Python Process RAM ==="
$procs = Get-Process python -ErrorAction SilentlyContinue
if ($procs) {
    foreach ($p in $procs) {
        $rss = [math]::Round($p.WorkingSet64/1MB, 1)
        $vm = [math]::Round($p.VirtualMemorySize64/1MB, 1)
        Write-Host "PID=$($p.Id)  RSS=${rss}MB  VM=${vm}MB"
    }
    $total = ($procs | Measure-Object -Property WorkingSet64 -Sum).Sum
    Write-Host "TOTAL RSS: $([math]::Round($total/1MB, 1))MB"
} else {
    Write-Host "No Python processes found"
}
