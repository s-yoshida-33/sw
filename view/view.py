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
logging.getLogger('comtypes').setLevel(logging.WARNING)

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
active_channel = None
preloaded_images = {}  # channel -> ImageTk.PhotoImage

# Audio (dedicated thread to avoid COM conflict with Tkinter)
_audio_queue = queue.Queue()

def _audio_worker():
    volumes = []  # COM objects must stay alive within this thread
    try:
        pythoncom.CoInitialize()

        try:
            from comtypes.client import CreateObject
            from pycaw.api.mmdeviceapi import IMMDeviceEnumerator
            from pycaw.constants import CLSID_MMDeviceEnumerator
            enumerator = CreateObject(
                CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator
            )
            # DEVICE_STATEMASK_ALL=15: active + disabled + unplugged endpoints
            collection = enumerator.EnumAudioEndpoints(0, 15)
            for i in range(collection.GetCount()):
                try:
                    device = collection.Item(i)
                    iface = device.Activate(
                        IAudioEndpointVolume._iid_, CLSCTX_ALL, None
                    )
                    volumes.append(cast(iface, POINTER(IAudioEndpointVolume)))
                except Exception:
                    pass
        except Exception:
            # fallback: default endpoint only
            try:
                dev = getattr(AudioUtilities.GetSpeakers(), '_dev',
                              AudioUtilities.GetSpeakers())
                iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volumes.append(cast(iface, POINTER(IAudioEndpointVolume)))
            except Exception:
                pass

        logging.info(f"Audio initialized ({len(volumes)} endpoint(s))")

        while True:
            state = _audio_queue.get()
            if state is None:
                break
            mute_val = 1 if state else 0
            for volume in volumes:
                try:
                    volume.SetMute(mute_val, None)
                except Exception:
                    pass
            try:
                for session in AudioUtilities.GetAllSessions():
                    try:
                        session.SimpleAudioVolume.SetMute(mute_val, None)
                    except Exception:
                        pass
            except Exception:
                pass


    except Exception as e:
        logging.warning(f"Audio init failed: {e}")
    finally:
        volumes.clear()  # release COM objects within this thread before CoUninitialize
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

def set_mute(state):
    _audio_queue.put(state)

def close_audio():
    _audio_queue.put(None)

# Preload all images at startup (must run on main thread)
def preload_images():
    global preloaded_images
    if not IMAGE_BASE_PATH.exists():
        IMAGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
        logging.warning(f"Image dir created: {IMAGE_BASE_PATH}")
    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    paths = {}
    for ext in [".jpg", ".png"]:  # png takes priority over jpg
        for path in IMAGE_BASE_PATH.glob(f"DI_View_*{ext}"):
            try:
                paths[int(path.stem.split('_')[-1])] = path
            except ValueError:
                pass
    for channel, path in sorted(paths.items()):
        try:
            img = Image.open(path)
            img.thumbnail((w, h), Image.Resampling.LANCZOS)
            bg = Image.new('RGB', (w, h), 'black')
            bg.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
            preloaded_images[channel] = ImageTk.PhotoImage(bg)
        except Exception as e:
            logging.error(f"Preload error {path}: {e}")
    logging.info(f"Preloaded {len(preloaded_images)} image(s)")

# Load image (uses preloaded cache)
def load_image(channel):
    global current_image
    if channel in preloaded_images:
        current_image = preloaded_images[channel]
        image_label.configure(image=current_image)
        image_label.image = current_image
        return True
    image_label.configure(image='', text="No Image", font=("Arial", 36), fg="white")
    return False

# Update display (runs on main thread via root.after)
def update_display(channel, state):
    global active_channel
    if state == 1:
        logging.info(f"Signal ON: DI{channel}")
        active_channel = channel
        if load_image(channel):
            root.deiconify()
            root.lift()
            root.focus_force()
            root.attributes("-topmost", True)
            set_mute(True)
        else:
            root.deiconify()
    else:
        if channel != active_channel:
            return
        logging.info(f"Signal OFF: DI{channel}")
        active_channel = None
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
    preload_images()
    threading.Thread(target=start_osc_server, daemon=True).start()

    try:
        root.mainloop()
    except Exception as e:
        logging.error(f"Tkinter error: {e}")
    finally:
        safe_quit()
        print("\nExiting...\nProgram ended")
