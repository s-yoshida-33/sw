# srv.py v2.3

import time
from pymodbus.client import ModbusTcpClient
import paho.mqtt.client as mqtt
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import socket
import os
import csv
from datetime import datetime
import logging
import base64
from pathlib import Path

# Logging
LOG_DIR = Path("C:/sw/logs") / datetime.now().strftime("%Y-%m-%d")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'srv.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Default settings
ADAM_IP = "192.168.11.105"
MODBUS_PORT = 502
DI_CHANNEL_COUNT = 16
MQTT_BROKER = "192.168.11.106"
MQTT_PORT = 1883
MQTT_TOPIC = "adam6250/di"
DOMAIN_NAME = "adam"
WEB_PORT = 80

# Config file
config_file = Path("C:/sw/config/config.txt")

# Load config
if config_file.exists():
    with config_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key == "ADAM_IP": ADAM_IP = value
            elif key == "MODBUS_PORT": MODBUS_PORT = int(value)
            elif key == "DI_CHANNEL_COUNT": DI_CHANNEL_COUNT = int(value)
            elif key == "MQTT_BROKER": MQTT_BROKER = value
            elif key == "MQTT_PORT": MQTT_PORT = int(value)
            elif key == "MQTT_TOPIC": MQTT_TOPIC = value
            elif key == "DOMAIN_NAME": DOMAIN_NAME = value
            elif key == "WEB_PORT": WEB_PORT = int(value)

# Globals
current_signal_str = "OFF"
last_signal_str = "OFF"
di_bits = [0]*DI_CHANNEL_COUNT
communication_logs = []
max_logs = 100
csv_log_file = LOG_DIR / 'srv_log.csv'
IMAGE_BASE_PATH = Path("C:/sw/images")

# Write CSV log
def write_csv_log(log_type, source, message, status="SUCCESS"):
    try:
        file_exists = csv_log_file.exists()
        with csv_log_file.open('a' if file_exists else 'w', encoding='utf-8', newline='') as csvfile:
            fieldnames = ['timestamp', 'type', 'source', 'message', 'status', 'signal']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'type': log_type,
                'source': source,
                'message': message,
                'status': status,
                'signal': current_signal_str
            })
    except Exception as e:
        logging.error(f"CSV write error: {e}")

def add_communication_log(log_type, source, message, status="SUCCESS"):
    global communication_logs
    log_entry = {
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'type': log_type,
        'source': source,
        'message': message,
        'status': status,
        'signal': current_signal_str
    }
    communication_logs.insert(0, log_entry)
    communication_logs = communication_logs[:max_logs]
    write_csv_log(log_type, source, message, status)
    if status == "ERROR":
        logging.error(f"{source}: {message}")
    else:
        logging.info(f"{source}: {message}")

# Ensure HTML directory
def ensure_html_files():
    Path("html").mkdir(exist_ok=True)
    logging.info("HTML check complete")

# Load image for DI status
def get_signal_image(di_bits):
    for i, bit in enumerate(di_bits):
        if bit:
            for ext in [".png", ".jpg"]:
                image_path = IMAGE_BASE_PATH / f"DI_View_{i}{ext}"
                if image_path.exists():
                    try:
                        with open(image_path, 'rb') as f:
                            return base64.b64encode(f.read()).decode('utf-8')
                    except Exception as e:
                        logging.error(f"Image read error: {e}")
    return None

# Web server handler
class SimpleHandler(BaseHTTPRequestHandler):
    HTML_DIR = Path("C:/sw/html")
    
    def do_GET(self):
        try:
            routes = {
                '/': (self.HTML_DIR / 'index.html', 'text/html'),
                '/monitor': (self.HTML_DIR / 'monitor.html', 'text/html'),
                '/monitor/': (self.HTML_DIR / 'monitor.html', 'text/html')
            }
            if self.path in routes:
                self.serve_file(*routes[self.path])
            elif self.path == '/api/status':
                self.handle_api_status()
            elif self.path == '/api/download_csv':
                self.handle_csv_download()
            else:
                self.send_error(404)
        except Exception as e:
            add_communication_log("WEB", self.client_address[0], f"Error: {str(e)}", "ERROR")
            self.send_error(500)
    
    def serve_file(self, filepath, content_type):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', f'{content_type}; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode('utf-8'))
            add_communication_log("WEB", self.client_address[0], f"Access: {filepath}", "SUCCESS")
        except FileNotFoundError:
            self.send_error(404)
    
    def handle_api_status(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        status = {
            'signal': current_signal_str,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'image_data': get_signal_image(di_bits),
            'logs': communication_logs[:20]
        }
        self.wfile.write(json.dumps(status, ensure_ascii=False).encode('utf-8'))
    
    def handle_csv_download(self):
        try:
            if os.path.exists(csv_log_file):
                self.send_response(200)
                self.send_header('Content-type', 'text/csv; charset=shift-jis')
                self.send_header('Content-Disposition',
                               f'attachment; filename="srv_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"')
                self.end_headers()
                with open(csv_log_file, 'rb') as f:
                    self.wfile.write(f.read())
                add_communication_log("CSV", self.client_address[0], "CSV download", "SUCCESS")
            else:
                self.send_error(404)
        except Exception as e:
            add_communication_log("CSV", self.client_address[0], f"Error: {str(e)}", "ERROR")
            self.send_error(500)

    def log_message(self, format, *args):
        pass

# Start web server
def start_web_server(port=None):
    if port is None:
        port = WEB_PORT

    local_ip = MQTT_BROKER

    print("\n" + "="*60)
    print(" Switch System - Web server started")
    print("="*60)
    print(f"\nCMS URL:")
    print(f"  http://{local_ip}:{port}/monitor/")
    print("\n" + "="*60 + "\n")

    try:
        server = HTTPServer(('0.0.0.0', port), SimpleHandler)
        add_communication_log("SERVER", "System", f"Web server started port:{port}", "SUCCESS")
        server.serve_forever()
    except OSError:
        if port == 80:
            logging.warning(f"Port 80 busy, retrying on 8080...")
            start_web_server(8080)
        else:
            logging.error(f"Port {port} failed to start")

# Main process
def main():
    global current_signal_str, di_bits, last_signal_str

    print("\n" + "="*60)
    print(" Switch System - Server started")
    print(f"\nMQTT Broker URL: mqtt://{socket.gethostbyname(socket.gethostname())}:{MQTT_PORT}")
    print("="*60)
    
    ensure_html_files()

    # MQTT connect
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    def on_connect(client, userdata, flags, reason_code, properties):
        status = "SUCCESS" if reason_code == 0 else "ERROR"
        msg = "Connected" if reason_code == 0 else f"Failed (rc={reason_code})"
        add_communication_log("MQTT", MQTT_BROKER, msg, status)
    mqtt_client.on_connect = on_connect
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
    except Exception as e:
        add_communication_log("MQTT", MQTT_BROKER, f"Connect failed: {str(e)}", "ERROR")
    
    # Modbus connect
    MODBUS_RECONNECT_INTERVAL = 30
    last_modbus_attempt = 0
    client_modbus = ModbusTcpClient(ADAM_IP, port=MODBUS_PORT)
    if not client_modbus.connect():
        add_communication_log("MODBUS", ADAM_IP, "ADAM-6250 connect failed", "ERROR")
        client_modbus = None
        last_modbus_attempt = time.time()
    else:
        add_communication_log("MODBUS", ADAM_IP, "ADAM-6250 connected", "SUCCESS")

    # Start web server
    threading.Thread(target=start_web_server, daemon=True).start()

    # Main loop
    try:
        while True:
            # Reconnect if disconnected
            if client_modbus is None:
                if time.time() - last_modbus_attempt >= MODBUS_RECONNECT_INTERVAL:
                    last_modbus_attempt = time.time()
                    client_modbus = ModbusTcpClient(ADAM_IP, port=MODBUS_PORT)
                    if not client_modbus.connect():
                        add_communication_log("MODBUS", ADAM_IP, "ADAM-6250 reconnect failed", "ERROR")
                        client_modbus = None
                    else:
                        add_communication_log("MODBUS", ADAM_IP, "ADAM-6250 reconnected", "SUCCESS")

            if client_modbus:
                try:
                    rr = client_modbus.read_discrete_inputs(address=0, count=DI_CHANNEL_COUNT)
                    di_bits = rr.bits if not rr.isError() else [0]*DI_CHANNEL_COUNT

                    signal_str = "OFF"
                    for i, bit in enumerate(di_bits):
                        if bit:
                            signal_str = f"ON [DI-{i}]"
                            break

                    if signal_str != last_signal_str:
                        add_communication_log("MODBUS", ADAM_IP, f"Signal changed: {last_signal_str} → {signal_str}", "SUCCESS")
                        last_signal_str = signal_str
                except Exception as e:
                    add_communication_log("MODBUS", ADAM_IP, f"Error: {str(e)}", "ERROR")
                    di_bits = [0]*DI_CHANNEL_COUNT
                    signal_str = "OFF"
                    try:
                        client_modbus.close()
                    except Exception:
                        pass
                    client_modbus = None
                    last_modbus_attempt = time.time()
            else:
                di_bits = [0]*DI_CHANNEL_COUNT
                signal_str = "OFF"

            current_signal_str = signal_str
            mqtt_client.publish(MQTT_TOPIC, current_signal_str)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        if client_modbus:
            client_modbus.close()
        mqtt_client.loop_stop()
        print("Program ended")

if __name__ == "__main__":
    main()