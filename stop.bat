@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$c = Get-NetTCPConnection -LocalPort 8770 -State Listen -ErrorAction SilentlyContinue;" ^
  "if (-not $c) { Write-Host 'Instructoravs is not running.'; exit 0 }" ^
  "$p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue;" ^
  "if ($p -and $p.ProcessName -like 'python*') {" ^
  "  $p | Stop-Process -Force; Write-Host ('Stopped Instructoravs (pid ' + $p.Id + ').')" ^
  "} else { Write-Host 'Port 8770 is held by another process; nothing was stopped.' }"
pause
