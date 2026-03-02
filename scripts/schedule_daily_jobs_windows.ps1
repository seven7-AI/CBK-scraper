# Create two Windows Task Scheduler tasks to run the CBK scraper and OCR
# jobs daily in production.
#
# - Scraper job at 10:00 AM:  python -m cbk_scraper.run
# - OCR job at 12:00 PM:      python -m cbk_ocr.run_ocr
#
# Usage (from project root, PowerShell):
#   .\scripts\schedule_daily_jobs_windows.ps1
# Optional custom times:
#   .\scripts\schedule_daily_jobs_windows.ps1 -ScraperHour 9 -OcrHour 11

param(
    [int] $ScraperHour = 10,
    [int] $ScraperMinute = 0,
    [int] $OcrHour = 12,
    [int] $OcrMinute = 0
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$PythonExe = if (Test-Path $VenvPython) { $VenvPython } else { (Get-Command python -ErrorAction SilentlyContinue).Source }
if (-not $PythonExe) {
    Write-Error "Python not found. Create a venv in project root: python -m venv .venv"
    exit 1
}

# Scraper task (10:00 by default)
$ScraperAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m cbk_scraper.run" -WorkingDirectory $ProjectRoot
$ScraperTrigger = New-ScheduledTaskTrigger -Daily -At "$($ScraperHour):$($ScraperMinute.ToString('00'))"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName "CBK-Scraper-10AM" -Action $ScraperAction -Trigger $ScraperTrigger -Settings $Settings -Principal $Principal -Force

# OCR task (12:00 by default)
$OcrAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "-m cbk_ocr.run_ocr" -WorkingDirectory $ProjectRoot
$OcrTrigger = New-ScheduledTaskTrigger -Daily -At "$($OcrHour):$($OcrMinute.ToString('00'))"

Register-ScheduledTask -TaskName "CBK-OCR-12PM" -Action $OcrAction -Trigger $OcrTrigger -Settings $Settings -Principal $Principal -Force

Write-Host "Scheduled tasks created:"
Write-Host " - 'CBK-Scraper-10AM' at $($ScraperHour):$($ScraperMinute.ToString('00'))"
Write-Host " - 'CBK-OCR-12PM' at $($OcrHour):$($OcrMinute.ToString('00'))"
Write-Host "To run now: Start-ScheduledTask -TaskName 'CBK-Scraper-10AM'; Start-ScheduledTask -TaskName 'CBK-OCR-12PM'"
Write-Host "To remove later: Unregister-ScheduledTask -TaskName 'CBK-Scraper-10AM'; Unregister-ScheduledTask -TaskName 'CBK-OCR-12PM'"

