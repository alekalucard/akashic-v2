Write-Host "=== cards.json sizes ==="
Get-ChildItem -Path "F:\Sandbox\failure_factory\akashic_v2" -Recurse -Filter "cards.json" -ErrorAction SilentlyContinue | ForEach-Object {
    $sizeMB = [math]::Round($_.Length/1MB, 1)
    Write-Host "$sizeMB MB  $($_.FullName)"
}

Write-Host ""
Write-Host "=== Other large JSON ==="
Get-ChildItem -Path "F:\Sandbox\failure_factory\akashic_v2" -Recurse -Filter "*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 10MB } | ForEach-Object {
    $sizeMB = [math]::Round($_.Length/1MB, 1)
    Write-Host "$sizeMB MB  $($_.FullName)"
}
