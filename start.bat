@echo off
cd /d "%~dp0"

REM ── Try pythonw (no window) from PATH ────────────────────────────────────
where pythonw >nul 2>&1
if %errorlevel% == 0 (
    start "" pythonw compressor.py
    goto :end
)

REM ── Try pythonw from AppData local Python install ─────────────────────────
set LOCAL_PY=%LOCALAPPDATA%\Programs\Python
for /d %%D in ("%LOCAL_PY%\Python3*") do (
    if exist "%%D\pythonw.exe" (
        start "" "%%D\pythonw.exe" compressor.py
        goto :end
    )
)

REM ── Try pre-built exe ─────────────────────────────────────────────────────
if exist "dist\compressor.exe" (
    start "" "dist\compressor.exe"
    goto :end
)

REM ── Fallback: python with window (last resort) ────────────────────────────
where python >nul 2>&1
if %errorlevel% == 0 (
    start "" python compressor.py
    goto :end
)

echo ERROR: Python not found. Install from https://python.org
pause

:end
