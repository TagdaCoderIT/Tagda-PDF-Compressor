import os
import sys
import json
import time
import glob
import shutil
import logging
import tempfile
import threading
import subprocess
from pathlib import Path
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor

# ── Third-party (installed via pip) ──────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

try:
    from plyer import notification as plyer_notification
    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False

# ── Global shared state ───────────────────────────────────────────────────────
paused_event = threading.Event()
paused_event.set()          # set = running; clear = paused

config: dict = {}
gs_path: str | None = None
executor: ThreadPoolExecutor | None = None
observer: "Observer | None" = None
tray_icon: "pystray.Icon | None" = None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_base_dir() -> Path:
    """Return the directory that contains this script / the frozen .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_bundled_asset(filename: str) -> Path:
    """
    Return path to a file that was bundled by PyInstaller via --add-data.
    Falls back to get_base_dir() when running as plain script.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / filename
        if candidate.exists():
            return candidate
    return get_base_dir() / filename


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

DEFAULTS = {
    "watch_folder": os.path.expandvars("%USERPROFILE%\\Downloads"),
    "max_size_kb": 200,
    "min_size_kb": 100,
    "wait_seconds": 2,
    "notification": True,
    "log_file": "compressor.log",
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)

    # Prefer the editable copy next to the exe/script; fall back to bundle
    for candidate in [get_base_dir() / "config.json", get_bundled_asset("config.json")]:
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    user = json.load(f)
                cfg.update(user)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[WARN] Could not read {candidate}: {exc}. Using defaults.")
            break

    # Expand environment variables in watch_folder
    cfg["watch_folder"] = os.path.expandvars(cfg["watch_folder"])
    cfg["watch_folder"] = os.path.expanduser(cfg["watch_folder"])

    # Resolve log_file to absolute path
    log_path = Path(cfg["log_file"])
    if not log_path.is_absolute():
        log_path = get_base_dir() / log_path
    cfg["log_file"] = str(log_path)

    # Type coercions / validation
    for int_key in ("max_size_kb", "min_size_kb", "wait_seconds"):
        try:
            cfg[int_key] = int(cfg[int_key])
        except (TypeError, ValueError):
            cfg[int_key] = DEFAULTS[int_key]
    cfg["notification"] = bool(cfg.get("notification", True))

    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def setup_logging(log_path: str):
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Rotating file handler — 5 MB × 3 files
    fh = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=3,
                             encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler (suppressed in --windowed builds but harmless)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)


# ─────────────────────────────────────────────────────────────────────────────
# Ghostscript detection
# ─────────────────────────────────────────────────────────────────────────────

def find_ghostscript() -> "str | None":
    candidates: list[str] = []

    # 1. Portable copy alongside this script / exe
    local_gs = get_base_dir() / "gs" / "bin" / "gswin64c.exe"
    if local_gs.exists():
        candidates.append(str(local_gs))

    # 2. Windows Registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript")
        i = 0
        while True:
            try:
                version = winreg.EnumKey(key, i)
                subkey = winreg.OpenKey(key, version)
                dll_path, _ = winreg.QueryValueEx(subkey, "GS_DLL")
                bin_dir = Path(dll_path).parent
                for exe_name in ("gswin64c.exe", "gswin32c.exe"):
                    exe = bin_dir / exe_name
                    if exe.exists():
                        candidates.append(str(exe))
                i += 1
            except OSError:
                break
    except Exception:
        pass

    # 3. Common install paths
    for pattern in (
        "C:/Program Files/gs/gs*/bin/gswin64c.exe",
        "C:/Program Files (x86)/gs/gs*/bin/gswin64c.exe",
        "C:/Program Files/gs/gs*/bin/gswin32c.exe",
    ):
        candidates.extend(glob.glob(pattern))

    # 4. PATH
    for name in ("gswin64c", "gswin32c", "gs"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    # Verify each candidate
    for path in candidates:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True, timeout=5, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                logging.info(f"Ghostscript found: {path} (v{result.stdout.strip()})")
                return path
        except Exception:
            continue

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Icon generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_icon() -> Path:
    icon_path = get_base_dir() / "icon.png"
    if icon_path.exists():
        return icon_path

    # Check bundled asset (PyInstaller)
    bundled = get_bundled_asset("icon.png")
    if bundled.exists() and bundled != icon_path:
        shutil.copy2(bundled, icon_path)
        return icon_path

    if not HAS_TRAY:
        # pystray / Pillow not installed yet; skip generation
        return icon_path

    # Auto-generate a simple red PDF icon
    size = 64
    img = Image.new("RGB", (size, size), color=(200, 45, 45))
    draw = ImageDraw.Draw(img)
    # White border rectangle
    draw.rectangle([4, 4, size - 5, size - 5], outline=(255, 255, 255), width=3)
    # "PDF" text — use default font (no external font needed)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()
    draw.text((14, 22), "PDF", fill=(255, 255, 255), font=font)
    img.save(icon_path)
    return icon_path


# ─────────────────────────────────────────────────────────────────────────────
# Notifications
# ─────────────────────────────────────────────────────────────────────────────

def send_notification(title: str, message: str):
    if not config.get("notification", True):
        return
    logging.info(f"NOTIFY: {title} — {message}")
    if HAS_PLYER:
        try:
            plyer_notification.notify(
                title=title,
                message=message,
                app_name="Tagda PDF Compressor",
                timeout=6,
            )
            return
        except Exception as exc:
            logging.debug(f"plyer notification failed: {exc}")
    # Fallback: Windows balloon tip via ctypes (works without plyer)
    try:
        import ctypes
        ctypes.windll.user32.MessageBeep(0)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# PDF utilities
# ─────────────────────────────────────────────────────────────────────────────

def is_valid_pdf(path: Path) -> bool:
    """Lightweight check: valid PDF header + EOF marker."""
    try:
        size = path.stat().st_size
        if size < 16:
            return False
        with open(path, "rb") as f:
            header = f.read(8)
            if not header.startswith(b"%PDF-"):
                return False
            seek_back = min(1024, size)
            f.seek(-seek_back, 2)
            tail = f.read()
        return b"%%EOF" in tail
    except OSError:
        return False


def wait_for_download(path: str, wait_sec: int) -> bool:
    """
    Block until the file size has been stable for `wait_sec` consecutive
    seconds (indicating the download is complete).
    Returns False if the file disappears or the wait exceeds 5 minutes.
    """
    deadline = time.time() + 300  # 5-minute absolute timeout
    stable_since: "float | None" = None
    last_size = -1

    while time.time() < deadline:
        try:
            current_size = os.path.getsize(path)
            # Also verify the file can be opened (not exclusively locked)
            with open(path, "rb"):
                pass
        except OSError:
            return False  # file gone or still exclusively locked for too long

        if current_size == last_size:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= wait_sec:
                return True
        else:
            stable_since = None
            last_size = current_size

        time.sleep(1)

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Compression
# ─────────────────────────────────────────────────────────────────────────────

# Ghostscript compression level definitions.
# Each entry is a list of extra args appended to the base command.
COMPRESSION_LEVELS = [
    # Level 0 — screen quality (72 dpi), maximum compression
    ["-dPDFSETTINGS=/screen"],
    # Level 1 — screen + forced 50 dpi downsampling
    [
        "-dPDFSETTINGS=/screen",
        "-dDownsampleColorImages=true", "-dColorImageResolution=50",
        "-dDownsampleGrayImages=true",  "-dGrayImageResolution=50",
        "-dDownsampleMonoImages=true",  "-dMonoImageResolution=50",
    ],
    # Level 2 — grayscale + aggressive (nuclear option)
    [
        "-dPDFSETTINGS=/screen",
        "-dDownsampleColorImages=true", "-dColorImageResolution=50",
        "-dDownsampleGrayImages=true",  "-dGrayImageResolution=50",
        "-dDownsampleMonoImages=true",  "-dMonoImageResolution=50",
        "-sColorConversionStrategy=Gray",
        "-dProcessColorModel=/DeviceGray",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/FlateEncode",
    ],
]


def compress_pdf(input_path: str, cfg: dict) -> "tuple[bool, int, int]":
    """
    Attempt to compress a PDF to under cfg['max_size_kb'].

    Returns (success, original_kb, final_kb).
    On success the original file is replaced in-place.
    """
    global gs_path

    original_size = os.path.getsize(input_path)
    original_kb = original_size // 1024

    if original_kb < cfg["min_size_kb"]:
        logging.info(f"SKIP {Path(input_path).name} — already {original_kb} KB (< {cfg['min_size_kb']} KB)")
        return False, original_kb, original_kb

    if gs_path is None:
        logging.warning(f"SKIP {Path(input_path).name} — Ghostscript not available")
        return False, original_kb, original_kb

    max_kb = cfg["max_size_kb"]
    best_path: "Path | None" = None
    best_kb = original_kb

    tmp_dir = Path(tempfile.mkdtemp(prefix="pdfcomp_"))
    try:
        base_args = [
            gs_path,
            "-dNOPAUSE", "-dBATCH", "-dQUIET",
            "-sDEVICE=pdfwrite",
            "-dCompatibilityLevel=1.4",
        ]

        for level_idx, extra_args in enumerate(COMPRESSION_LEVELS):
            # Respect pause between levels
            paused_event.wait()

            out_path = tmp_dir / f"level{level_idx}.pdf"
            cmd = base_args + extra_args + [
                f"-sOutputFile={out_path}",
                input_path,
            ]

            try:
                result = subprocess.run(cmd, capture_output=True, timeout=180)
            except subprocess.TimeoutExpired:
                logging.warning(f"GS level {level_idx} timed out for {Path(input_path).name}")
                continue

            if result.returncode != 0:
                logging.warning(
                    f"GS level {level_idx} failed (rc={result.returncode}): "
                    f"{result.stderr.decode(errors='replace').strip()[:200]}"
                )
                continue

            if not out_path.exists() or out_path.stat().st_size == 0:
                logging.warning(f"GS level {level_idx} produced empty output")
                continue

            if not is_valid_pdf(out_path):
                logging.warning(f"GS level {level_idx} produced invalid PDF")
                continue

            compressed_kb = out_path.stat().st_size // 1024
            logging.debug(
                f"{Path(input_path).name}: level {level_idx} → {compressed_kb} KB"
            )

            if compressed_kb < best_kb:
                best_kb = compressed_kb
                best_path = out_path

            if best_kb < max_kb:
                # Already under the ceiling — no need to go harder
                break

        # ── Decision ──────────────────────────────────────────────────────────
        if best_path is None:
            logging.warning(f"All GS levels failed for {Path(input_path).name}")
            return False, original_kb, original_kb

        if best_kb >= original_kb:
            logging.info(
                f"{Path(input_path).name}: compression did not reduce size "
                f"({original_kb} KB → {best_kb} KB). Keeping original."
            )
            return False, original_kb, best_kb

        if best_kb > max_kb:
            logging.warning(
                f"{Path(input_path).name}: best compressed size {best_kb} KB "
                f"still exceeds target {max_kb} KB. Keeping original."
            )
            return False, original_kb, best_kb

        # Replace original atomically (copy2 overwrites, no new FS create event)
        shutil.copy2(str(best_path), input_path)
        logging.info(
            f"COMPRESSED {Path(input_path).name}: {original_kb} KB → {best_kb} KB "
            f"(saved {original_kb - best_kb} KB)"
        )
        return True, original_kb, best_kb

    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Worker
# ─────────────────────────────────────────────────────────────────────────────

def process_pdf(file_path: str):
    """Runs on a worker thread. Full pipeline for one PDF file."""
    try:
        name = Path(file_path).name

        # 1. Wait until download is fully written to disk
        if not wait_for_download(file_path, config.get("wait_seconds", 5)):
            logging.warning(f"File not stable / disappeared: {file_path}")
            return

        # 2. Respect pause
        paused_event.wait()

        # 3. Re-check size (may have changed while waiting)
        try:
            size_kb = os.path.getsize(file_path) // 1024
        except OSError:
            logging.warning(f"File disappeared before processing: {file_path}")
            return

        if size_kb < config.get("min_size_kb", 200):
            logging.info(f"SKIP {name} — {size_kb} KB (already small enough)")
            return

        # 4. Compress
        success, orig_kb, final_kb = compress_pdf(file_path, config)

        # 5. Notify
        if success:
            msg = f"{name}: {orig_kb} KB → {final_kb} KB"
            send_notification("PDF Compressed", msg)
        else:
            if final_kb < orig_kb:
                logging.info(f"{name}: could not meet target (best {final_kb} KB from {orig_kb} KB)")
            # no notification for skipped / already-small files

    except Exception:
        logging.exception(f"Unexpected error processing {file_path}")


# ─────────────────────────────────────────────────────────────────────────────
# Watchdog
# ─────────────────────────────────────────────────────────────────────────────

def on_new_file(event):
    """Called from the watchdog Observer thread."""
    if event.is_directory:
        return

    # For 'moved' events (Chrome: .crdownload → .pdf), use dest_path
    if hasattr(event, "dest_path"):
        file_path = event.dest_path
    else:
        file_path = event.src_path

    if not file_path.lower().endswith(".pdf"):
        return

    logging.debug(f"Detected: {file_path} ({event.event_type})")
    if executor:
        executor.submit(process_pdf, file_path)


class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        on_new_file(event)

    def on_moved(self, event):
        # Chromium browsers rename .crdownload → .pdf on completion
        on_new_file(event)


# ─────────────────────────────────────────────────────────────────────────────
# System tray
# ─────────────────────────────────────────────────────────────────────────────

def make_menu():
    status_label = "⏸ Paused" if not paused_event.is_set() else "● Running"
    toggle_label = "Resume" if not paused_event.is_set() else "Pause"
    return pystray.Menu(
        pystray.MenuItem(status_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(toggle_label, _toggle_pause),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", _quit_app),
    )


def _toggle_pause(icon, item):
    if paused_event.is_set():
        paused_event.clear()
        logging.info("Compression paused by user")
    else:
        paused_event.set()
        logging.info("Compression resumed by user")
    icon.menu = make_menu()
    icon.update_menu()


def _quit_app(icon, item):
    logging.info("Quit requested from system tray")
    icon.stop()
    if observer:
        observer.stop()
    if executor:
        executor.shutdown(wait=False)
    # sys.exit called after icon.run() returns in main()


def setup_tray(icon_path: Path) -> "pystray.Icon":
    try:
        img = Image.open(icon_path)
    except Exception:
        # Fallback: create a plain red square in memory
        img = Image.new("RGB", (64, 64), color=(200, 45, 45))

    icon = pystray.Icon(
        name="Tagda PDF Compressor",
        icon=img,
        title="Tagda PDF Compressor",
        menu=make_menu(),
    )
    return icon


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global config, gs_path, executor, observer, tray_icon

    # ── 1. Config ─────────────────────────────────────────────────────────────
    config = load_config()

    # ── 2. Logging ────────────────────────────────────────────────────────────
    setup_logging(config["log_file"])
    logging.info("=" * 60)
    logging.info("Tagda PDF Compressor starting")
    logging.info(f"  Watch folder : {config['watch_folder']}")
    logging.info(f"  Skip below   : {config['min_size_kb']} KB")
    logging.info(f"  Target max   : {config['max_size_kb']} KB")
    logging.info(f"  Wait stable  : {config['wait_seconds']} sec")
    logging.info(f"  Log file     : {config['log_file']}")
    logging.info("=" * 60)

    # ── 3. Icon ───────────────────────────────────────────────────────────────
    icon_path = generate_icon()

    # ── 4. Ghostscript ────────────────────────────────────────────────────────
    gs_path = find_ghostscript()
    if gs_path is None:
        logging.critical(
            "Ghostscript NOT found. Compression is disabled. "
            "Run install_gs.bat to install it."
        )
        send_notification(
            "Tagda PDF Compressor",
            "Ghostscript not found — compression disabled. Run install_gs.bat.",
        )
    else:
        logging.info(f"Ghostscript: {gs_path}")

    # ── 5. Verify watch folder exists ─────────────────────────────────────────
    watch_dir = config["watch_folder"]
    if not os.path.isdir(watch_dir):
        logging.warning(f"Watch folder does not exist: {watch_dir}")

    # ── 6. Thread pool ────────────────────────────────────────────────────────
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="pdf_worker")

    # ── 7. File watcher ───────────────────────────────────────────────────────
    if HAS_WATCHDOG:
        observer = Observer()
        observer.schedule(PDFHandler(), watch_dir, recursive=False)
        observer.daemon = True
        observer.start()
        logging.info(f"Watching: {watch_dir}")
    else:
        logging.critical(
            "watchdog not installed. Run: pip install watchdog plyer pystray Pillow"
        )

    # ── 8. System tray (blocks main thread) ───────────────────────────────────
    if HAS_TRAY:
        tray_icon = setup_tray(icon_path)
        logging.info("Tagda PDF Compressor running. Right-click tray icon to pause/quit.")
        tray_icon.run()     # ← BLOCKS until _quit_app calls icon.stop()
    else:
        # Fallback: no tray — just keep the main thread alive
        logging.warning(
            "pystray / Pillow not installed. Running without tray icon. "
            "Press Ctrl+C to stop."
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Stopped by Ctrl+C")

    # ── 9. Cleanup (runs after tray exits) ────────────────────────────────────
    if observer:
        observer.stop()
        observer.join(timeout=5)
    executor.shutdown(wait=False)
    logging.info("Tagda PDF Compressor stopped cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    main()
