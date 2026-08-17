$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$UpdateScript = Join-Path $ProjectRoot "scripts\update_weekly.ps1"
$PowerShell = (Get-Command powershell.exe -ErrorAction Stop).Source
$Action = New-ScheduledTaskAction -Execute $PowerShell -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$UpdateScript`""
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 8am
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
Register-ScheduledTask -TaskName "SystMacro FX Weekly Update" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Refresh BIS FX factors and validate the SystMacro dashboard" -Force
Write-Output "Installed weekly task: SystMacro FX Weekly Update (Mondays at 08:00 local time)."

