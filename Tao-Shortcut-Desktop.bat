@echo off
REM ============================================================================
REM  Tao icon "SynthaData GUI" tren DESKTOP cua may HIEN TAI.
REM  Chay 1 lan sau khi `git pull` ve may moi -> shortcut tro dung duong dan may
REM  do (khong dung duong dan cung). Double-click file nay.
REM ============================================================================
setlocal
set "PROJDIR=%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$proj=$env:PROJDIR.TrimEnd('\');" ^
  "$desk=[Environment]::GetFolderPath('Desktop');" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut((Join-Path $desk 'SynthaData GUI.lnk'));" ^
  "$s.TargetPath=(Join-Path $proj 'SynthaData-GUI.vbs');" ^
  "$s.WorkingDirectory=$proj;" ^
  "$s.IconLocation=((Join-Path $proj 'synthadata.ico')+',0');" ^
  "$s.Description='SynthaData - sinh du lieu tong hop (GUI)';" ^
  "$s.Save();" ^
  "Write-Host ('[OK] Da tao shortcut tren desktop: ' + $desk + '\SynthaData GUI.lnk')"

echo.
echo Xong! Ra desktop, bam dup "SynthaData GUI" (icon luoi xanh-tim) de mo app.
echo.
pause
endlocal
