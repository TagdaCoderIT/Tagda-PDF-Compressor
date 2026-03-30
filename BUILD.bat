@echo off
title PDF Compressor - Build to .exe
cd /d "%~dp0"
echo ============================================================
echo   PDF Compressor -- PyInstaller Build Script
echo ============================================================
echo.

REM ── Check Python ─────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found on PATH.
    echo Install from https://python.org  ^(tick "Add to PATH" during install^)
    pause & exit /b 1
)
echo Python found:
python --version
echo.

REM ── Step 1: Install dependencies ─────────────────────────────────────────
echo [1/3] Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install watchdog plyer pystray Pillow pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo   OK.
echo.

REM ── Step 2: Generate icon if missing ─────────────────────────────────────
echo [2/3] Checking icon.png...
if not exist "icon.png" (
    echo   Generating icon.png...
    python -c "from PIL import Image, ImageDraw; sz=64; img=Image.new('RGB',(sz,sz),(200,45,45)); d=ImageDraw.Draw(img); d.rectangle([4,4,sz-5,sz-5],outline=(255,255,255),width=3); img.save('icon.png'); print('  icon.png created')"
)
echo   icon.png OK.
echo.

REM ── Step 3: PyInstaller ───────────────────────────────────────────────────
echo [3/3] Building compressor.exe (this takes 1-2 minutes)...
echo.

REM Clean old build
if exist "build"              rmdir /s /q "build"
if exist "dist\compressor.exe" del /q "dist\compressor.exe"
if exist "compressor.spec"    del /q "compressor.spec"

REM Single build run
if exist "icon.png" (
    python -m PyInstaller --onefile --windowed --name compressor --icon "icon.png" --add-data "config.json;." --add-data "icon.png;." --hidden-import "plyer.platforms.win.notification" --hidden-import "pystray._win32" --hidden-import "PIL._tkinter_finder" --hidden-import "watchdog.observers.winapi" compressor.py
) else (
    python -m PyInstaller --onefile --windowed --name compressor --add-data "config.json;." --hidden-import "plyer.platforms.win.notification" --hidden-import "pystray._win32" --hidden-import "PIL._tkinter_finder" --hidden-import "watchdog.observers.winapi" compressor.py
)

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed. See output above for details.
    pause & exit /b 1
)

echo.
echo ============================================================
echo   BUILD SUCCESSFUL  --  dist\compressor.exe
echo ============================================================
echo.
echo   To deploy on another PC:
echo     1. Copy  dist\compressor.exe  +  config.json
echo     2. Run   install_gs.bat  on the target PC
echo     3. Double-click  compressor.exe
echo.
pause
