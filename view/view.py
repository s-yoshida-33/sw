# view.py v3.0

import tkinter as tk
from PIL import Image, ImageTk
from pathlib import Path
import logging
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import pythoncom
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import threading
import queue
from datetime import datetime
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

# Logging
LOG_DIR = Path("C:/sw/logs") / datetime.now().strftime("%Y-%m-%d")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "view.log", encoding="utf-8")
    ]
)

# Default settings
IMAGE_BASE_PATH = Path("C:/sw/images")
OSC_PORT = 9000

# Config file
config_file = Path("C:/sw/config/config.txt")

if config_file.exists():
    with config_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "OSC_PORT": OSC_PORT = int(value)

# Tkinter init
root = tk.Tk()
root.title("DI Display")
root.configure(bg="black")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.withdraw()
image_label = tk.Label(root, bg="black")
image_label.pack(fill=tk.BOTH, expand=True)

# State
current_image = None

# Audio (dedicated thread to avoid COM conflict with Tkinter)
_audio_queue = queue.Queue()

def _audio_worker():
    try:
        pythoncom.CoInitialize()
        devices = AudioUtilities.GetSpeakers()
        dev = getattr(devices, '_dev', devices)
        interface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        logging.info("Audio initialized")
        while True:
            state = _audio_queue.get()
            if state is None:
                break
            volume.SetMute(1 if state else 0, None)
            logging.info(f"Audio mute: {state}")
    except Exception as e:
        logging.warning(f"Audio init failed: {e}")
    finally:
        try:
            pythoncom.CoUninitialize()
        except:
            pass

def set_mute(state):
    _audio_queue.put(state)

def close_audio():
    _audio_queue.put(None)

# Load image
def load_image(channel):
    global current_image
    for ext in [".png", ".jpg"]:
        image_path = IMAGE_BASE_PATH / f"DI_View_{channel}{ext}"
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
    image_label.configure(image='', text="No Image", font=("Arial", 36), fg="white")
    return False

# Update display (runs on main thread via root.after)
def update_display(channel, state):
    if state == 1:
        logging.info(f"Signal ON: DI{channel}")
        if load_image(channel):
            root.deiconify()
            root.lift()
            root.attributes("-topmost", True)
            set_mute(True)
        else:
            root.deiconify()
    else:
        logging.info(f"Signal OFF: DI{channel}")
        root.withdraw()
        set_mute(False)

# OSC handler (runs on OSC thread)
def di_handler(address, *args):
    try:
        channel = int(address.split('/')[-1])
        state = int(args[0]) if args else 1
        root.after(0, update_display, channel, state)
    except Exception as e:
        logging.error(f"OSC parse error: address={address} args={args} - {e}")

# Safe quit
def safe_quit():
    try:
        close_audio()
        root.quit()
    except:
        pass

# Check images
def check_images():
    if not IMAGE_BASE_PATH.exists():
        IMAGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
        logging.warning(f"Image dir created: {IMAGE_BASE_PATH}")
    images = list(IMAGE_BASE_PATH.glob("DI_View_*.png")) + list(IMAGE_BASE_PATH.glob("DI_View_*.jpg"))
    logging.info(f"Detected image files: {len(images)}")

# Start OSC server
def start_osc_server():
    dispatcher = Dispatcher()
    dispatcher.map("/di/*", di_handler)
    server = ThreadingOSCUDPServer(("0.0.0.0", OSC_PORT), dispatcher)
    logging.info(f"OSC server listening on UDP port {OSC_PORT}")
    server.serve_forever()

# Main
if __name__ == "__main__":
    print("\n" + "="*50)
    print(" DI Display System (OSC/UDP)")
    print("="*50)
    print(f" Images : {IMAGE_BASE_PATH}")
    print(f" OSC Port: {OSC_PORT}")
    print("="*50 + "\n")

    threading.Thread(target=_audio_worker, daemon=True).start()
    check_images()
    threading.Thread(target=start_osc_server, daemon=True).start()

    try:
        root.mainloop()
    except Exception as e:
        logging.error(f"Tkinter error: {e}")
    finally:
        safe_quit()
        print("\nExiting...\nProgram ended")
