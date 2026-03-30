@echo off
title Ghostscript Installer for PDF Compressor
cd /d "%~dp0"
echo ============================================================
echo   Ghostscript Auto-Installer for PDF Compressor
echo ============================================================
echo.

REM ── Already in PATH? ─────────────────────────────────────────────────────
where gswin64c >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript already installed:
    gswin64c --version
    goto :done
)
where gswin32c >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript ^(32-bit^) already installed:
    gswin32c --version
    goto :done
)

REM ── Portable copy next to script? ────────────────────────────────────────
if exist "%~dp0gs\bin\gswin64c.exe" (
    echo Local portable Ghostscript found at gs\bin\gswin64c.exe
    goto :done
)

REM ── Already installed (registry)? ────────────────────────────────────────
reg query "HKLM\SOFTWARE\GPL Ghostscript" >nul 2>&1
if %errorlevel% == 0 (
    echo Ghostscript is installed ^(found in registry^).
    echo It will be detected automatically by PDF Compressor.
    goto :done
)

REM ── Download and install ──────────────────────────────────────────────────
echo Ghostscript not found. Downloading now...
echo.

set GS_VER=10.07.0
set GS_VER_NODOT=10070
set GS_EXE=gs%GS_VER_NODOT%w64.exe
set GS_URL=https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs%GS_VER_NODOT%/%GS_EXE%
set GS_TMP=%TEMP%\%GS_EXE%

echo Version : %GS_VER%
echo File    : %GS_EXE%
echo.
echo Downloading... (may take a minute)

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%GS_URL%' -OutFile '%GS_TMP%' -UseBasicParsing"

if not exist "%GS_TMP%" (
    echo.
    echo ERROR: Download failed.
    echo.
    echo Please download manually:
    echo   https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10070/gs10070w64.exe
    echo Then double-click to install, then restart PDF Compressor.
    pause & exit /b 1
)

echo Download complete. Installing silently ^(needs admin rights^)...
echo.

"%GS_TMP%" /S

if %errorlevel% neq 0 (
    echo Silent install failed. Opening interactive installer...
    "%GS_TMP%"
)

del "%GS_TMP%" >nul 2>&1

echo.
echo Verifying...

set FOUND=0
for /d %%V in ("C:\Program Files\gs\gs*") do (
    if exist "%%V\bin\gswin64c.exe" (
        echo SUCCESS: Ghostscript installed at %%V\bin\
        "%%V\bin\gswin64c.exe" --version
        set FOUND=1
    )
)

if "%FOUND%"=="0" (
    echo Installed but not yet on PATH.
    echo Restart your PC or reopen CMD to refresh PATH.
    echo PDF Compressor will still find it via registry automatically.
)

goto :end

:done
echo.
echo Ghostscript is ready. No action needed.

:end
echo.
pause
