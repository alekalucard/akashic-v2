#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs Akashic MCP as a Windows Service
.DESCRIPTION
    One-click installer for the Akashic MCP SSE server.
    After installation, the service:
    - Starts automatically on Windows boot
    - Restarts on crash
    - Runs invisibly in background
    - Claude Code connects via http://127.0.0.1:8765/sse
#>

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "$Root\.venv\Scripts\python.exe"

# Verify venv exists
if (-not (Test-Path $Python)) {
    Write-Host "[ERROR] Virtual environment not found at: $Python" -ForegroundColor Red
    Write-Host "Create it with: python -m venv .venv && .venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AKASHIC MCP SERVICE INSTALLER" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click and select 'Run with PowerShell as Administrator'" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Running as Administrator" -ForegroundColor Green

# Navigate to project root
Set-Location $Root
Write-Host "[OK] Working directory: $Root" -ForegroundColor Green

# Check Python
try {
    $pyVersion = & $Python --version 2>&1
    Write-Host "[OK] Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python not found in PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check pywin32
Write-Host "[..] Checking pywin32..." -ForegroundColor Gray
$pywin32Check = & $Python -c "import win32serviceutil; print('OK')" 2>&1
if ($pywin32Check -ne "OK") {
    Write-Host "[..] Installing pywin32..." -ForegroundColor Yellow
    & $Python -m pip install pywin32 --quiet
    # Run post-install script
    & $Python -m pywin32_postinstall -install 2>$null
}
Write-Host "[OK] pywin32 ready" -ForegroundColor Green

# Kill anything on port 8765 first
$portProcess = Get-NetTCPConnection -LocalPort 8765 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($portProcess) {
    Write-Host "[..] Killing existing process on port 8765 (PID: $portProcess)..." -ForegroundColor Yellow
    Stop-Process -Id $portProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

# Check if service already exists
$existingService = Get-Service -Name "AkashicMCP" -ErrorAction SilentlyContinue
if ($existingService) {
    if ($existingService.Status -eq "Running") {
        Write-Host "[OK] Service already running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "MCP Endpoint: http://127.0.0.1:8765/sse" -ForegroundColor Cyan
        Read-Host "Press Enter to close"
        exit 0
    }
    Write-Host "[..] Existing service found (stopped), starting..." -ForegroundColor Yellow
    Start-Service -Name "AkashicMCP" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $svc = Get-Service -Name "AkashicMCP"
    if ($svc.Status -eq "Running") {
        Write-Host "[OK] Service started!" -ForegroundColor Green
        Write-Host "MCP Endpoint: http://127.0.0.1:8765/sse" -ForegroundColor Cyan
        Read-Host "Press Enter to close"
        exit 0
    }
    Write-Host "[..] Service failed to start, reinstalling..." -ForegroundColor Yellow
    & $Python mcp_service.py stop 2>$null
    Start-Sleep -Seconds 1
    & $Python mcp_service.py remove 2>$null
    Start-Sleep -Seconds 1
}

# Install service
Write-Host "[..] Installing Akashic MCP Service..." -ForegroundColor Cyan
& $Python mcp_service.py install
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Service installation failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Service installed" -ForegroundColor Green

# Start service
Write-Host "[..] Starting service..." -ForegroundColor Cyan
& $Python mcp_service.py start
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Service failed to start" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Service started" -ForegroundColor Green

# Verify
Start-Sleep -Seconds 2
$service = Get-Service -Name "AkashicMCP" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Service Name:   AkashicMCP" -ForegroundColor White
    Write-Host "Status:         Running" -ForegroundColor White
    Write-Host "Startup:        Automatic" -ForegroundColor White
    Write-Host "MCP Endpoint:   http://127.0.0.1:8765/sse" -ForegroundColor White
    Write-Host ""
    Write-Host "Claude Code will auto-connect on restart." -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "[WARN] Service may not be running correctly" -ForegroundColor Yellow
    Write-Host "Check services.msc for 'Akashic MCP Server'" -ForegroundColor Yellow
}

Read-Host "Press Enter to close"
