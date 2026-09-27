#Requires -RunAsAdministrator
# One-time setup for MCP autostart via Task Scheduler

$taskName = "AkashicMCP"
$pythonw = "F:\Sandbox\failure_factory\akashic_v2\.venv\Scripts\pythonw.exe"
$script = "F:\Sandbox\failure_factory\akashic_v2\mcp_service.py"
$workDir = "F:\Sandbox\failure_factory\akashic_v2"

Write-Host "Setting up AkashicMCP autostart..." -ForegroundColor Cyan

# Remove old task if exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Remove old broken Windows service if exists
sc.exe stop AkashicMCP 2>$null
sc.exe delete AkashicMCP 2>$null

# Create new task
$action = New-ScheduledTaskAction -Execute $pythonw -Argument "$script run" -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -RunLevel Highest -Force

Write-Host ""
Write-Host "Done! MCP server will auto-start on login." -ForegroundColor Green
Write-Host "Starting it now..." -ForegroundColor Cyan

Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 3
$result = Invoke-WebRequest -Uri "http://127.0.0.1:8765/sse" -Method Head -TimeoutSec 2 -ErrorAction SilentlyContinue
if ($result.StatusCode -eq 200) {
    Write-Host "Server is running!" -ForegroundColor Green
} else {
    Write-Host "Server may still be starting..." -ForegroundColor Yellow
}

Read-Host "Press Enter to close"
