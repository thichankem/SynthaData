@echo off
REM Mở giao diện đồ hoạ (GUI) cho SynthaData. Double-click để chạy.
REM Ưu tiên Python của Anaconda (có pip + các thư viện đã cài), sau đó fallback.
setlocal
cd /d "%~dp0"

set "PY=%USERPROFILE%\anaconda3\python.exe"
if exist "%PY%" goto run

REM Fallback: Python launcher hoặc python trong PATH.
where py >nul 2>nul && (set "PY=py" & goto run)
set "PY=python"

:run
"%PY%" -m synthadata --gui
if errorlevel 1 (
  echo.
  echo [Loi] Khong mo duoc GUI. Kiem tra da cai dependencies:  pip install -r requirements.txt
  pause
)
endlocal
