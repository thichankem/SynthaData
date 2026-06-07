@echo off
REM ============================================================================
REM  Mo giao dien (GUI) SynthaData. Double-click de chay.
REM  TU DO Python co du thu vien (test 'import yaml') -> chay duoc tren MAY KHAC
REM  sau khi `git pull`, khong phu thuoc duong dan cung. Bo qua Python thieu lib
REM  (vd msys2). Uu tien pythonw.exe -> khong hien cua so console.
REM ============================================================================
setlocal enableextensions enabledelayedexpansion
cd /d "%~dp0"

REM --- Cac THU MUC Python uu tien (anaconda/miniconda/standard) ---
set "DIRS=%CONDA_PREFIX%;%USERPROFILE%\anaconda3;%USERPROFILE%\miniconda3;%ProgramData%\anaconda3;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python310"

for %%D in ("%DIRS:;=" "%") do (
  if not "%%~D"=="" if exist "%%~D\python.exe" (
    "%%~D\python.exe" -c "import yaml" >nul 2>nul && (
      start "" "%%~D\pythonw.exe" -m synthadata --gui
      goto :done
    )
  )
)

REM --- Fallback: pythonw / python / py tren PATH (van kiem tra co thu vien) ---
for %%E in (pythonw python) do (
  where %%E >nul 2>nul && ( %%E -c "import yaml" >nul 2>nul && (
      start "" %%E -m synthadata --gui
      goto :done
  ))
)
where py >nul 2>nul && ( py -c "import yaml" >nul 2>nul && (
    start "" py -m synthadata --gui
    goto :done
))

echo.
echo [Loi] Khong tim thay Python co du thu vien.
echo   Cai Python 3 (khuyen nghi Anaconda) roi chay:  pip install -r requirements.txt
echo.
pause
exit /b 1

:done
endlocal
exit /b 0
