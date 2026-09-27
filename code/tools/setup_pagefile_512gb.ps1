# Setup 512GB Pagefile on D: drive
# ============================================
# Must be run as Administrator!
# After running, a REBOOT is required.
# ============================================

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Must run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as Administrator, then run this script" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== Akashic Pagefile Setup ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Disable automatic pagefile management
Write-Host "[1/4] Disabling automatic pagefile management..." -ForegroundColor Yellow
$cs = Get-CimInstance Win32_ComputerSystem
if ($cs.AutomaticManagedPagefile) {
    Set-CimInstance -InputObject $cs -Property @{AutomaticManagedPagefile=$false}
    Write-Host "  -> Automatic management disabled" -ForegroundColor Green
} else {
    Write-Host "  -> Already disabled" -ForegroundColor Green
}

# Step 2: Remove existing pagefiles (except we'll keep C: as a small backup)
Write-Host "[2/4] Checking existing pagefiles..." -ForegroundColor Yellow
$existing = Get-CimInstance Win32_PageFileSetting
foreach ($pf in $existing) {
    Write-Host "  Found: $($pf.Name) (Init: $($pf.InitialSize)MB, Max: $($pf.MaximumSize)MB)"
}

# Step 3: Set C: pagefile to small (4GB min, 8GB max) as backup
Write-Host "[3/4] Configuring pagefiles..." -ForegroundColor Yellow

# Remove all existing first
Get-CimInstance Win32_PageFileSetting | Remove-CimInstance

# C: small backup pagefile (4-8GB)
# Note: Win32_PageFileSetting requires [uint32] for size properties
try {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name = "C:\pagefile.sys"
        InitialSize = [uint32]4096
        MaximumSize = [uint32]8192
    } | Out-Null
    Write-Host "  -> C:\pagefile.sys: 4GB - 8GB (backup)" -ForegroundColor Green
} catch {
    Write-Host "  CIM failed, trying WMI fallback..." -ForegroundColor Yellow
    $null = Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{
        Name = "C:\pagefile.sys"
        InitialSize = 4096
        MaximumSize = 8192
    }
    Write-Host "  -> C:\pagefile.sys: 4GB - 8GB (backup) [via WMI]" -ForegroundColor Green
}

# D: main pagefile (512GB fixed)
$targetDrive = "D:"
$targetSize = 524288  # 512 * 1024 = 524288 MB

# Verify D: has space
$disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$targetDrive'"
$freeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
Write-Host "  -> $targetDrive has ${freeGB}GB free" -ForegroundColor Cyan

if ($freeGB -lt 520) {
    Write-Host "  ERROR: Not enough space on $targetDrive! Need 520GB free." -ForegroundColor Red
    Write-Host "  Trying E: instead..." -ForegroundColor Yellow
    $targetDrive = "E:"
    $disk = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$targetDrive'"
    $freeGB = [math]::Round($disk.FreeSpace / 1GB, 1)
    Write-Host "  -> $targetDrive has ${freeGB}GB free" -ForegroundColor Cyan
}

try {
    New-CimInstance -ClassName Win32_PageFileSetting -Property @{
        Name = "${targetDrive}\pagefile.sys"
        InitialSize = [uint32]$targetSize
        MaximumSize = [uint32]$targetSize
    } | Out-Null
    Write-Host "  -> ${targetDrive}\pagefile.sys: 512GB (fixed)" -ForegroundColor Green
} catch {
    Write-Host "  CIM failed, trying WMI fallback..." -ForegroundColor Yellow
    $null = Set-WmiInstance -Class Win32_PageFileSetting -Arguments @{
        Name = "${targetDrive}\pagefile.sys"
        InitialSize = $targetSize
        MaximumSize = $targetSize
    }
    Write-Host "  -> ${targetDrive}\pagefile.sys: 512GB (fixed) [via WMI]" -ForegroundColor Green
}

# Step 4: Summary
Write-Host ""
Write-Host "[4/4] Configuration complete!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Current settings (will take effect after reboot):" -ForegroundColor Yellow
Get-CimInstance Win32_PageFileSetting | Format-Table Name, InitialSize, MaximumSize -AutoSize

$totalVirtual = 31.8 + 512 + 8  # RAM + D: pagefile + C: pagefile
Write-Host "After reboot, total virtual memory will be ~${totalVirtual}GB" -ForegroundColor Green
Write-Host "  Physical RAM:    31.8 GB" -ForegroundColor White
Write-Host "  D: Pagefile:     512 GB" -ForegroundColor White
Write-Host "  C: Pagefile:     4-8 GB" -ForegroundColor White
Write-Host ""
Write-Host ">>> REBOOT REQUIRED to apply changes <<<" -ForegroundColor Red
Write-Host ""
$reboot = Read-Host "Reboot now? (y/n)"
if ($reboot -eq 'y') {
    Write-Host "Rebooting in 10 seconds... (Ctrl+C to cancel)" -ForegroundColor Red
    Start-Sleep -Seconds 10
    Restart-Computer -Force
} else {
    Write-Host "Remember to reboot for changes to take effect!" -ForegroundColor Yellow
}
