# signal_logger.py
# Logs DI signal changes seen by the broker, independent of any STB, so the
# server-side history can be cross-checked against each STB's view-*.log.

import re
import time
import zipfile
import logging
from pathlib import Path
from datetime import datetime
import paho.mqtt.client as mqtt

# Config file (MQTT_BROKER is ignored: this runs on the broker's own machine)
MQTT_PORT = 1883
MQTT_TOPIC = "kc868a16/di"
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
            if key == "MQTT_PORT": MQTT_PORT = int(value)
            elif key == "MQTT_TOPIC": MQTT_TOPIC = value
MQTT_BROKER = "127.0.0.1"

# Logging
LOG_DIR = Path("C:/sw/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / f"signal-{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)

# Log retention: mirrors view.py (see view/view.py). This process restarts
# daily via SrvDailyRestart, so a startup-time check is enough.
DAILY_LOG_RE = re.compile(r"^signal-(\d{4}-\d{2})-\d{2}\.log$")
MONTHLY_ZIP_RE = re.compile(r"^signal-(\d{4})-(\d{2})\.zip$")
ZIP_RETENTION_MONTHS = 12

def archive_past_month_logs():
    current_month = datetime.now().strftime("%Y-%m")
    months = {}
    for log_file in LOG_DIR.glob("signal-*.log"):
        m = DAILY_LOG_RE.match(log_file.name)
        if m and m.group(1) != current_month:
            months.setdefault(m.group(1), []).append(log_file)
    for month, files in months.items():
        zip_path = LOG_DIR / f"signal-{month}.zip"
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
    for zip_file in LOG_DIR.glob("signal-*.zip"):
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

# Parse DI channel index from payload (same interpretation as view.py)
DI_PAYLOAD_RE = re.compile(r"^(?:ON\s*\[DI-(\d+)\]|(\d+))$", re.IGNORECASE)

def parse_di_index(payload):
    if payload.upper() == "OFF":
        return None
    m = DI_PAYLOAD_RE.match(payload)
    if not m:
        return None
    return int(m.group(1) or m.group(2))

current_signal_str = "OFF"

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        logging.info("MQTT connected")
        client.subscribe(MQTT_TOPIC)
    else:
        logging.error(f"MQTT connect failed: rc={reason_code}")

def on_message(client, userdata, msg):
    global current_signal_str
    payload = msg.payload.decode().strip()
    di_index = parse_di_index(payload)
    signal_str = "OFF" if di_index is None else f"ON [DI-{di_index}]"
    if signal_str != current_signal_str:
        logging.info(f"Signal changed: {current_signal_str} \u2192 {signal_str}")
        current_signal_str = signal_str

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def connect_mqtt():
    connected = False
    while not connected:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
            connected = True
            logging.info(f"MQTT connected: {MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC}")
        except Exception as e:
            logging.error(f"MQTT error: {e}, retry in 5 sec")
            time.sleep(5)

if __name__ == "__main__":
    print("\n" + "="*50)
    print(" Signal Logger - started")
    print(f" MQTT: {MQTT_BROKER}:{MQTT_PORT}, topic={MQTT_TOPIC}")
    print("="*50 + "\n")

    archive_past_month_logs()
    cleanup_old_archives()
    connect_mqtt()
    mqtt_client.loop_forever()
