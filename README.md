# TagdaPDF-Compressor

A background PDF auto-compressor for Windows. Watches your Downloads folder and automatically compresses any PDF that is larger than the configured size — silently, with a desktop notification when done.

---

## How It Works

```
New PDF detected in Downloads
        │
        ▼
Wait until download is complete (file size stable for 2 sec)
        │
        ▼
Already under 100 KB? → SKIP
        │
        ▼
Try compression (Level 1 → Level 2 → Level 3)
        │
        ▼
Result under 200 KB and smaller than original? → REPLACE
        │
        ▼
Desktop notification: "invoice.pdf: 3.2 MB → 190 KB"
```

---

## Prerequisites

Before using this project, install the following on your PC:

### 1. Python 3.10 or higher
- Download from: https://www.python.org/downloads/
- During install, **tick "Add Python to PATH"** — this is important

### 2. Ghostscript (PDF compression engine)
- Run the included `install_gs.bat` (see setup steps below), OR
- Download manually: https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10070/gs10070w64.exe
- Run the installer as Administrator

### 3. Python packages
Run this once in Command Prompt:
```
pip install watchdog plyer pystray Pillow pyinstaller
```

---

## Clone the Project

Open Command Prompt and run:

```bash
git clone https://github.com/TagdaCoderIT/TagdaPDF-Compressor.git
cd TagdaPDF-Compressor
```

Or download as ZIP from GitHub → click **Code → Download ZIP** → extract it.

---

## Setup (First Time)

### Step 1 — Install Ghostscript
Right-click `install_gs.bat` → **Run as administrator**

This will automatically download and install Ghostscript on your PC.
If you already downloaded `gs10070w64.exe`, just double-click it to install.

### Step 2 — Install Python packages
Open Command Prompt in the project folder and run:
```
pip install watchdog plyer pystray Pillow
```

### Step 3 — Run it
Double-click `start.bat`

A red **PDF** icon will appear in your system tray (bottom-right of taskbar).
The compressor is now running in the background.

---

## Configuration

Edit `config.json` to change settings:

```json
{
    "watch_folder": "%USERPROFILE%\\Downloads",
    "max_size_kb": 200,
    "min_size_kb": 100,
    "wait_seconds": 5,
    "notification": true,
    "log_file": "compressor.log"
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `watch_folder` | `~/Downloads` | Folder to watch for new PDFs |
| `max_size_kb` | `200` | Target output size in KB |
| `min_size_kb` | `100` | Skip PDFs already smaller than this |
| `wait_seconds` | `5` | Seconds to wait for download to complete |
| `notification` | `true` | Show desktop notification after compression |
| `log_file` | `compressor.log` | Log file location |

---

## Build Portable .exe (No Python Needed)

To create a single `.exe` file that works on any Windows PC without Python:

1. Make sure Python and all packages are installed (see Prerequisites)
2. Double-click **`BUILD.bat`**
3. Wait 1–2 minutes for PyInstaller to finish
4. Output: `dist\compressor.exe`

### Deploy to another PC

Copy these files to the target PC:
```
compressor.exe   ← the built exe
config.json      ← settings file
install_gs.bat   ← to install Ghostscript on target PC
```

On the target PC:
1. Right-click `install_gs.bat` → Run as administrator
2. Double-click `compressor.exe`

> **Portable mode (no install at all):** Copy the Ghostscript `bin\` folder (containing `gswin64c.exe` + `gsdll64.dll`) into a subfolder named `gs\bin\` next to `compressor.exe`. The app will find it automatically without any system install.

---

## Auto-Start on PC Boot (Task Scheduler)

To make the compressor start automatically every time you log into Windows:

### Step 1 — Open Task Scheduler
Press `Win + R` → type `taskschd.msc` → press Enter

### Step 2 — Create a new task
Click **"Create Basic Task"** in the right panel

### Step 3 — Fill in the details

| Field | Value |
|-------|-------|
| Name | `PDF Compressor` |
| Trigger | **When I log on** |
| Action | **Start a program** |
| Program | Full path to `start.bat` or `compressor.exe` |
| Start in | Full path to the project folder |

Example paths:
```
Program:  C:\Users\YourName\Downloads\TagdaPDF-Compressor\start.bat
Start in: C:\Users\YourName\Downloads\TagdaPDF-Compressor
```

### Step 4 — Adjust task settings
After creating:
- Right-click the task → **Properties**
- **General** tab → select **"Run only when user is logged on"**
- Tick **"Run with highest privileges"**
- Click **OK**

The compressor will now auto-start silently every time you log in.

### To remove auto-start
Open Task Scheduler → find **PDF Compressor** → right-click → **Delete**

---

## Usage

| Action | How |
|--------|-----|
| Start | Double-click `start.bat` (or `compressor.exe`) |
| Pause | Right-click tray icon → **Pause** |
| Resume | Right-click tray icon → **Resume** |
| Stop | Right-click tray icon → **Quit** |
| View logs | Open `compressor.log` in the project folder |

---

## File Structure

```
TagdaPDF-Compressor/
├── compressor.py      ← Main script (watcher + compression + tray)
├── config.json        ← Settings
├── start.bat          ← Run without CMD window
├── BUILD.bat          ← Build portable .exe
├── install_gs.bat     ← Auto-install Ghostscript
├── icon.png           ← Tray icon (auto-generated on first run)
└── compressor.log     ← Compression history (auto-generated)
```

---

## Troubleshooting

**"Ghostscript not found" notification on startup**
→ Run `install_gs.bat` as Administrator, then restart the compressor.

**CMD window opens and closes but no tray icon**
→ Check `compressor.log` for errors. Usually means a missing Python package — run `pip install watchdog plyer pystray Pillow`.

**PDF not being compressed**
→ Check that the PDF is larger than `min_size_kb` (default 100 KB) in `config.json`.

**BUILD.bat fails**
→ Make sure Python is on PATH (`python --version` in CMD should work). Then retry.

---

## Tech Stack

| Component | Tool |
|-----------|------|
| Language | Python 3 |
| File Watching | `watchdog` |
| PDF Compression | Ghostscript |
| Notifications | `plyer` |
| System Tray | `pystray` + `Pillow` |
| Portable Build | PyInstaller |

---

## License

MIT License — free to use, modify, and distribute.
