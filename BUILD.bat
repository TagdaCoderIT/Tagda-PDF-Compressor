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
    echo Install from https://python.org  (tick "Add to PATH" during install)
    pause & exit /b 1
)
echo Python found:
python --version
echo.

REM ── Step 1: Install/upgrade dependencies ─────────────────────────────────
echo [1/4] Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install watchdog plyer pystray Pillow --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause & exit /b 1
)
echo   Dependencies OK.
echo.

REM ── Step 2: Install PyInstaller ──────────────────────────────────────────
echo [2/4] Installing PyInstaller...
python -m pip install pyinstaller --quiet
if %errorlevel% neq 0 (
    echo   Stable PyInstaller failed. Trying latest from GitHub (Python 3.14+ fix)...
    python -m pip install "https://github.com/pyinstaller/pyinstaller/archive/develop.zip" --quiet
    if %errorlevel% neq 0 (
        echo ERROR: Could not install PyInstaller.
        echo Try manually: pip install pyinstaller
        pause & exit /b 1
    )
)
echo   PyInstaller OK.
echo.

REM ── Step 3: Generate icon if missing ─────────────────────────────────────
echo [3/4] Checking icon.png...
if not exist "icon.png" (
    echo   Generating icon.png via Pillow...
    python -c "from PIL import Image, ImageDraw, ImageFont; sz=64; img=Image.new('RGB',(sz,sz),(200,45,45)); d=ImageDraw.Draw(img); d.rectangle([4,4,sz-5,sz-5],outline=(255,255,255),width=3); [setattr(d,'_font',None)]; img.save('icon.png'); print('  icon.png created')"
    if %errorlevel% neq 0 (
        echo   WARNING: Could not generate icon.png. Proceeding without custom icon.
    )
) else (
    echo   icon.png already exists.
)
echo.

REM ── Step 4: Run PyInstaller ───────────────────────────────────────────────
echo [4/4] Building compressor.exe...
echo.

REM Clean previous build artefacts
if exist "build" rmdir /s /q "build"
if exist "dist\compressor.exe" del /q "dist\compressor.exe"
if exist "compressor.spec" del /q "compressor.spec"

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name compressor ^
    --add-data "config.json;." ^
    --hidden-import "plyer.platforms.win.notification" ^
    --hidden-import "pystray._win32" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "watchdog.observers.winapi" ^
    --collect-submodules plyer ^
    --collect-submodules pystray ^
    compressor.py

REM Add icon only if it exists (avoids error when missing)
if exist "icon.png" (
    python -m PyInstaller ^
        --onefile ^
        --windowed ^
        --name compressor ^
        --icon "icon.png" ^
        --add-data "config.json;." ^
        --add-data "icon.png;." ^
        --hidden-import "plyer.platforms.win.notification" ^
        --hidden-import "pystray._win32" ^
        --hidden-import "PIL._tkinter_finder" ^
        --hidden-import "watchdog.observers.winapi" ^
        --collect-submodules plyer ^
        --collect-submodules pystray ^
        compressor.py
)

if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller build failed. See output above.
    pause & exit /b 1
)

echo.
echo ============================================================
echo   BUILD SUCCESSFUL
echo ============================================================
echo.
echo   Output: dist\compressor.exe
echo.
echo   Deployment:
echo     Copy dist\compressor.exe + config.json to any Windows PC.
echo     Ghostscript must also be installed on the target PC.
echo     Run install_gs.bat on the target PC if needed.
echo.
echo   Portable (no GS install needed):
echo     Also copy the gs\ folder (gswin64c.exe + gsdll64.dll)
echo     into the same folder as compressor.exe.
echo.
pause
