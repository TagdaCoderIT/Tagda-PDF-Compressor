@echo off
title Ghostscript Installer for PDF Compressor
cd /d "%~dp0"
echo ============================================================
echo   Ghostscript Auto-Installer for PDF Compressor
echo ============================================================
echo.

REM ── Check: already in PATH ───────────────────────────────────────────────
where gswin64c >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript already in PATH:
    gswin64c --version
    goto :already_done
)
where gswin32c >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript (32-bit) already in PATH:
    gswin32c --version
    goto :already_done
)

REM ── Check: portable copy next to this script ─────────────────────────────
if exist "%~dp0gs\bin\gswin64c.exe" (
    echo Local portable Ghostscript found at gs\bin\gswin64c.exe
    gs\bin\gswin64c --version
    goto :already_done
)

REM ── Check: registry (installed but not in PATH) ───────────────────────────
reg query "HKLM\SOFTWARE\GPL Ghostscript" >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript found in Windows registry but not on PATH.
    echo To fix: open System Properties ^> Environment Variables
    echo         and add the Ghostscript bin folder to PATH.
    echo         (Usually C:\Program Files\gs\gs*\bin)
    goto :already_done
)

REM ── Not found -- download and install ────────────────────────────────────
echo Ghostscript not found. Downloading installer...
echo.

set GS_VER=10.03.1
set GS_VER_NODOT=10031
set GS_EXE=gs%GS_VER_NODOT%w64.exe
set GS_URL=https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs%GS_VER_NODOT%/%GS_EXE%
set GS_TMP=%TEMP%\%GS_EXE%

echo Version : %GS_VER%
echo File    : %GS_EXE%
echo Source  : %GS_URL%
echo.
echo Downloading... (this may take a minute)
echo.

REM Use PowerShell to download with TLS 1.2
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; " ^
    "try { " ^
    "  Invoke-WebRequest -Uri '%GS_URL%' -OutFile '%GS_TMP%' -UseBasicParsing; " ^
    "  Write-Host 'Download complete.'; " ^
    "} catch { " ^
    "  Write-Host ('ERROR: ' + $_.Exception.Message); exit 1 " ^
    "}"

if not exist "%GS_TMP%" (
    echo.
    echo ERROR: Download failed.
    echo Please download manually from:
    echo   https://www.ghostscript.com/releases/gsdnld.html
    echo Then run the installer.
    pause & exit /b 1
)

echo.
echo Running silent installer (requires administrator privileges)...
echo.

REM NSIS-based installer supports /S for silent install
"%GS_TMP%" /S

if %errorlevel% neq 0 (
    echo.
    echo Silent install returned an error. Launching interactive installer...
    "%GS_TMP%"
)

REM Clean up installer file
del "%GS_TMP%" >nul 2>&1

echo.
echo Verifying installation...
echo.

REM Refresh PATH for this session by checking common install locations
set FOUND_GS=0
for /d %%V in ("C:\Program Files\gs\gs*") do (
    if exist "%%V\bin\gswin64c.exe" (
        echo SUCCESS: Ghostscript installed at %%V\bin\
        "%%V\bin\gswin64c.exe" --version
        set FOUND_GS=1
        goto :verify_done
    )
)
:verify_done

if "%FOUND_GS%"=="0" (
    where gswin64c >nul 2>&1
    if %errorlevel% == 0 (
        echo SUCCESS: Ghostscript now on PATH.
        gswin64c --version
        set FOUND_GS=1
    )
)

if "%FOUND_GS%"=="0" (
    echo.
    echo Ghostscript appears to have installed, but the exe was not found in
    echo common locations. You may need to restart your PC so PATH is refreshed.
    echo.
    echo The PDF Compressor will still find it via the Windows registry automatically.
)

goto :end

:already_done
echo.
echo Ghostscript is already available -- no action needed.

:end
echo.
pause
