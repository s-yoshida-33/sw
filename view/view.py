# view.py v2.4

import tkinter as tk
import paho.mqtt.client as mqtt
from PIL import Image, ImageTk
from pathlib import Path
import logging
import sys
import re
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import pythoncom
from pycaw.pycaw import AudioUtilities, EDataFlow, DEVICE_STATE
import time
import zipfile
import ctypes
from ctypes import wintypes
from datetime import datetime
from selector import SelectorController

# Logging
LOG_DIR = Path("C:/sw/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"view-{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ] + ([logging.StreamHandler()] if sys.stderr else [])  # no stderr under pythonw.exe
)

# Log retention: the STB reboots daily (signage app's own 3AM task), so a
# startup-time check is enough to catch every month boundary without needing
# an in-process timer.
DAILY_LOG_RE = re.compile(r"^view-(\d{4}-\d{2})-\d{2}\.log$")
MONTHLY_ZIP_RE = re.compile(r"^(\d{4})-(\d{2})\.zip$")
ZIP_RETENTION_MONTHS = 12

def archive_past_month_logs():
    current_month = datetime.now().strftime("%Y-%m")
    months = {}
    for log_file in LOG_DIR.glob("view-*.log"):
        m = DAILY_LOG_RE.match(log_file.name)
        if m and m.group(1) != current_month:
            months.setdefault(m.group(1), []).append(log_file)
    for month, files in months.items():
        zip_path = LOG_DIR / f"{month}.zip"
        try:
            with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as zf:
                for f in files:
                    zf.write(f, f.name)
            for f in files:
                f.unlink()
            logging.info(f"Archived {len(files)} log file(s) into {zip_path.name}")
        except Exception as e:
            logging.error(f"Log archive error ({month}): {e}")

def cleanup_old_archives():
    now = datetime.now()
    now_index = now.year * 12 + now.month
    for zip_file in LOG_DIR.glob("*.zip"):
        m = MONTHLY_ZIP_RE.match(zip_file.name)
        if not m:
            continue
        zip_index = int(m.group(1)) * 12 + int(m.group(2))
        if now_index - zip_index >= ZIP_RETENTION_MONTHS:
            try:
                zip_file.unlink()
                logging.info(f"Deleted expired log archive: {zip_file.name}")
            except Exception as e:
                logging.error(f"Log archive cleanup error ({zip_file.name}): {e}")

# Default settings
IMAGE_BASE_PATH = Path("C:/sw/images")
MQTT_BROKER = "192.168.11.106"
MQTT_PORT = 1883
MQTT_TOPIC = "kc868a16/di"
# Selector (IMAGENICS US-41 series) LAN control. Disabled when SELECTOR_HOST is empty.
SELECTOR_HOST = ""
SELECTOR_PORT = 1300
SELECTOR_INPUT = 0
SELECTOR_LOCK = True
SELECTOR_REASSERT_SEC = 5.0
# On OFF, the emergency image stays up until the selector is back on the original
# input; if the selector does not answer, it is hidden after this anyway.
SELECTOR_RESTORE_TIMEOUT_MS = 5000
# The selector already reports the original input to "w" while its output is still
# switching (about 2-3 s on site), so the image and mute are kept this much longer
# after the restore is confirmed.
SELECTOR_RESTORE_DELAY_MS = 4000

# Config file
config_file = Path("C:/sw/config/config.txt")

# Load config
if config_file.exists():
    with config_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "MQTT_BROKER": MQTT_BROKER = value
            elif key == "MQTT_PORT": MQTT_PORT = int(value)
            elif key == "MQTT_TOPIC": MQTT_TOPIC = value
            elif key == "SELECTOR_HOST": SELECTOR_HOST = value
            elif key == "SELECTOR_PORT": SELECTOR_PORT = int(value)
            elif key == "SELECTOR_INPUT": SELECTOR_INPUT = int(value)
            elif key == "SELECTOR_LOCK": SELECTOR_LOCK = value.lower() in ("1", "true", "yes", "on")
            elif key == "SELECTOR_REASSERT_SEC": SELECTOR_REASSERT_SEC = float(value)
            elif key == "SELECTOR_RESTORE_DELAY_MS": SELECTOR_RESTORE_DELAY_MS = int(value)

selector = None
if SELECTOR_HOST:
    if 1 <= SELECTOR_INPUT <= 4:
        selector = SelectorController(SELECTOR_HOST, SELECTOR_PORT, SELECTOR_INPUT, SELECTOR_LOCK, SELECTOR_REASSERT_SEC)
    else:
        logging.error(f"Selector control disabled: SELECTOR_INPUT must be 1-4 (got {SELECTOR_INPUT})")

# Tkinter init
root = tk.Tk()
root.title("Switch System Display")
root.configure(bg="black")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.withdraw()
image_label = tk.Label(root, bg="black")
image_label.pack(fill=tk.BOTH, expand=True)

# State
current_signal_str = "OFF"
off_seq = 0
current_image = None
saved_volumes = {}
is_muted = False

# Audio
def init_audio():
    try:
        pythoncom.CoInitialize()
    except Exception as e:
        logging.error(f"Audio init error: {e}")

# Devices may have more than one *active* render endpoint at once (e.g. an
# onboard "Speaker" device plus an HDMI-connected display's speakers set as
# the default communications device). Controlling only the single default
# device silently fails to mute audio that plays through the other one, so
# every active render endpoint is muted/restored, not just GetSpeakers().
def _active_render_devices():
    try:
        return AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
    except Exception as e:
        logging.error(f"Audio device enum error: {e}")
        return []

# Note: SetMute alone is not silenced over some remote-audio-capture paths
# (e.g. RustDesk), which follow the volume level but not the mute flag.
# Drive the volume level itself to 0 so muting is effective everywhere.
def set_mute(state):
    global saved_volumes, is_muted
    # update_display() calls set_mute(True) on every ON signal, including
    # ON -> ON transitions between different DI indexes. Without this guard,
    # a second call while already muted would re-read the current (already
    # zeroed) volume and clobber the originally saved value with 0.
    if state == is_muted:
        return
    for device in _active_render_devices():
        try:
            vol = device.EndpointVolume
            if state:
                saved_volumes[device.id] = vol.GetMasterVolumeLevelScalar()
                vol.SetMasterVolumeLevelScalar(0.0, None)
                vol.SetMute(1, None)
            else:
                vol.SetMute(0, None)
                if device.id in saved_volumes:
                    vol.SetMasterVolumeLevelScalar(saved_volumes[device.id], None)
        except Exception as e:
            logging.error(f"Audio mute error ({device.FriendlyName}): {e}")
    is_muted = state

def close_audio():
    try:
        pythoncom.CoUninitialize()
    except Exception as e:
        logging.error(f"Audio close error: {e}")

# Keep the emergency window on top. Tk's "-topmost" alone is not enough: signage
# apps that launch an external exe from their content (e.g. WonderScreenFactor's
# ZipApp) force that exe's window to the foreground (AttachThreadInput / a simulated
# Alt key press to get past Windows' foreground lock), and it then covers this
# window. While the image is shown, re-raise it to the top of the topmost band and
# take the foreground back whenever another window has it. The launcher only forces
# the exe forward until it succeeds once, so this does not turn into a tug of war.
KEEP_ON_TOP_INTERVAL_MS = 500

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
_user32.GetAncestor.restype = wintypes.HWND
_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SetForegroundWindow.restype = wintypes.BOOL
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.BringWindowToTop.restype = wintypes.BOOL
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]
_user32.SetWindowPos.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
_user32.AttachThreadInput.restype = wintypes.BOOL
_user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ctypes.c_size_t]
_user32.keybd_event.restype = None
_kernel32.GetCurrentThreadId.argtypes = []
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD

GA_ROOT = 2
HWND_TOPMOST = wintypes.HWND(-1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
# Whether the window has held the foreground since it was last shown; only losing
# it after that is logged (not the first raise on every ON).
had_foreground = False

def _window_hwnd():
    # winfo_id() is Tk's inner child window; the z-order belongs to its top-level frame.
    return _user32.GetAncestor(root.winfo_id(), GA_ROOT)

def force_to_front():
    global had_foreground
    hwnd = _window_hwnd()
    if not hwnd:
        return
    _user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    foreground = _user32.GetForegroundWindow()
    if foreground == hwnd:
        had_foreground = True
        return
    was_lost = had_foreground
    # Windows refuses SetForegroundWindow from a process that is not in the foreground,
    # so fall back to the same steps the launcher uses to push its exe forward.
    _user32.SetForegroundWindow(hwnd)
    if _user32.GetForegroundWindow() != hwnd and foreground:
        current = _kernel32.GetCurrentThreadId()
        other = _user32.GetWindowThreadProcessId(foreground, None)
        if other and other != current and _user32.AttachThreadInput(current, other, True):
            try:
                _user32.BringWindowToTop(hwnd)
                _user32.SetForegroundWindow(hwnd)
            finally:
                _user32.AttachThreadInput(current, other, False)
    if _user32.GetForegroundWindow() != hwnd:
        _user32.keybd_event(VK_MENU, 0, 0, 0)
        _user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        _user32.SetForegroundWindow(hwnd)
    regained = _user32.GetForegroundWindow() == hwnd
    if was_lost:
        logging.info(f"Emergency window lost the foreground to pid {_foreground_pid(foreground)}; "
                     + ("took it back" if regained else "could not take it back"))
    had_foreground = regained

def _foreground_pid(hwnd):
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value

def keep_on_top():
    try:
        if root.state() != "withdrawn":
            force_to_front()
    except Exception as e:
        logging.error(f"Keep-on-top error: {e}")
    root.after(KEEP_ON_TOP_INTERVAL_MS, keep_on_top)

# Load image
def load_image(di_index):
    global current_image
    for ext in [".png", ".jpg"]:
        image_path = IMAGE_BASE_PATH / f"DI_View_{di_index}{ext}"
        if image_path.exists():
            try:
                img = Image.open(image_path)
                w, h = root.winfo_screenwidth(), root.winfo_screenheight()
                img.thumbnail((w, h), Image.Resampling.LANCZOS)
                background = Image.new('RGB', (w, h), 'black')
                background.paste(img, ((w - img.width)//2, (h - img.height)//2))
                current_image = ImageTk.PhotoImage(background)
                image_label.configure(image=current_image)
                image_label.image = current_image
                return True
            except Exception as e:
                logging.error(f"Image load error: {e}")
                return False
    # No image
    image_label.configure(
        image='',
        text=f"No Image",
        font=("Arial", 36),
        fg="white"
    )
    return False

# Parse DI channel index from payload (no channel count limit)
DI_PAYLOAD_RE = re.compile(r"^(?:ON\s*\[DI-(\d+)\]|(\d+))$", re.IGNORECASE)

def parse_di_index(payload):
    if payload.upper() == "OFF":
        return None
    m = DI_PAYLOAD_RE.match(payload)
    if not m:
        return None
    return int(m.group(1) or m.group(2))

# Hide the emergency image and unmute. Ignored if the signal turned ON again, or if
# this is the fallback timer of an earlier OFF (seq mismatch).
def hide_emergency(seq=None):
    global had_foreground
    if current_signal_str != "OFF" or (seq is not None and seq != off_seq):
        return
    root.withdraw()
    had_foreground = False
    set_mute(False)

# Update display
def update_display(payload):
    global current_signal_str, off_seq
    payload = payload.strip()
    di_index = parse_di_index(payload)
    # Called on every message (incl. the 1s heartbeat) so a saved input is restored
    # even when view.py restarts after the emergency has ended.
    if selector:
        selector.request(di_index is not None)
    signal_str = "OFF" if di_index is None else f"ON [DI-{di_index}]"
    if signal_str != current_signal_str:
        logging.info(f"Signal changed: {current_signal_str} → {signal_str}")
        current_signal_str = signal_str
        if di_index is None:
            off_seq += 1
            if selector and selector.restore_pending():
                # Keep the image and mute until the selector has switched back. Hiding
                # first would briefly show (and sound) the STB's own content on the
                # emergency input before the original input comes back.
                # The fallback includes the post-restore delay, or it would fire first.
                root.after(SELECTOR_RESTORE_TIMEOUT_MS + SELECTOR_RESTORE_DELAY_MS, hide_emergency, off_seq)
            else:
                hide_emergency()
        else:
            if load_image(di_index):
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
                set_mute(True)
            else:
                root.deiconify()
            # Take the foreground now rather than on the next keep_on_top tick.
            root.update_idletasks()
            force_to_front()

# Safe quit
def safe_quit():
    try:
        if selector:
            selector.stop()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        close_audio()
        root.quit()
    except:
        pass

# MQTT
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("MQTT connected")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error(f"MQTT connect failed: rc={reason_code}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    root.after(0, update_display, payload)

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def connect_mqtt():
    global mqtt_client
    connected = False
    while not connected:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
            mqtt_client.loop_start()
            connected = True
            logging.info(f"MQTT connected: {MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC}")
            mqtt_client.subscribe(MQTT_TOPIC)
        except Exception as e:
            logging.error(f"MQTT error: {e}, retry in 5 sec")
            time.sleep(5)

# Check images
def check_images():
    if not IMAGE_BASE_PATH.exists():
        IMAGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
        logging.warning(f"Image dir created: {IMAGE_BASE_PATH}")
    images = list(IMAGE_BASE_PATH.glob("DI_View_*.png")) + list(IMAGE_BASE_PATH.glob("DI_View_*.jpg"))
    logging.info(f"Detected image files: {len(images)}")

# Main process
if __name__ == "__main__":
    print("\n" + "="*50)
    print(" Switch System - Display started")
    print("="*50)
    print(f" Images: {IMAGE_BASE_PATH}")
    print(f" MQTT: {MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC}")
    print("="*50 + "\n")

    archive_past_month_logs()
    cleanup_old_archives()
    init_audio()
    check_images()
    if selector:
        # Bind off_seq when the restore is confirmed (in the Tk thread), so a delayed hide
        # from this OFF does not cut short a later ON -> OFF.
        selector.on_restored = lambda: root.after(
            0, lambda: root.after(SELECTOR_RESTORE_DELAY_MS, hide_emergency, off_seq))
        selector.start()
    connect_mqtt()
    keep_on_top()

    try:
        root.mainloop()
    except Exception as e:
        logging.error(f"Tkinter error: {e}")
    finally:
        safe_quit()
        print("\nExiting...\nProgram ended")
