$action = New-ScheduledTaskAction -Execute 'C:\Program Files\Python311\pythonw.exe' -Argument '"C:\Users\Admin\router-agent\service_run.py"'
$triggerBoot = New-ScheduledTaskTrigger -AtStartup
$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName 'RouterControlServer' -Action $action -Trigger $triggerBoot,$triggerLogon -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName 'RouterControlServer'
Start-Sleep -Seconds 6
$t = Get-ScheduledTask -TaskName 'RouterControlServer'
Write-Output ("state=" + $t.State)
$li = Get-ScheduledTaskInfo -TaskName 'RouterControlServer'
Write-Output ("lastresult=" + $li.LastTaskResult)
