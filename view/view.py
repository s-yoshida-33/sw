# view.py v2.3

import tkinter as tk
import paho.mqtt.client as mqtt
from PIL import Image, ImageTk
from pathlib import Path
import logging
import re
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import pythoncom
from pycaw.pycaw import AudioUtilities, EDataFlow, DEVICE_STATE
import time
from datetime import datetime

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
MQTT_BROKER = "192.168.11.106"
MQTT_PORT = 1883
MQTT_TOPIC = "kc868a16/di"

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

# Update display
def update_display(payload):
    global current_signal_str
    payload = payload.strip()
    di_index = parse_di_index(payload)
    signal_str = "OFF" if di_index is None else f"ON [DI-{di_index}]"
    if signal_str != current_signal_str:
        logging.info(f"Signal changed: {current_signal_str} → {signal_str}")
        current_signal_str = signal_str
        if di_index is None:
            root.withdraw()
            set_mute(False)
        else:
            if load_image(di_index):
                root.deiconify()
                root.lift()
                root.attributes("-topmost", True)
                set_mute(True)
            else:
                root.deiconify()

# Safe quit
def safe_quit():
    try:
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

    init_audio()
    check_images()
    connect_mqtt()

    try:
        root.mainloop()
    except Exception as e:
        logging.error(f"Tkinter error: {e}")
    finally:
        safe_quit()
        print("\nExiting...\nProgram ended")
