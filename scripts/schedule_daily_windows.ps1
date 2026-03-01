# Create a Windows Task Scheduler task to run the CBK scraper daily (production).
# Run this script once from an elevated PowerShell, or run as Administrator.
# Usage: .\schedule_daily_windows.ps1
# Optional: .\schedule_daily_windows.ps1 -Hour 2 -Minute 0

param(
    [int] $Hour = 2,
    [int] $Minute = 0,
    [string] $TaskName = "CBK-Scraper-Daily"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $PythonExe) {
    Write-Error "Python not found. Create a venv in project root: python -m venv .venv"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m cbk_scraper.run" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "$($Hour):$($Minute.ToString('00'))"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
Write-Host "Scheduled task '$TaskName' created. Runs daily at $($Hour):$($Minute.ToString('00'))."
Write-Host "To run now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"
