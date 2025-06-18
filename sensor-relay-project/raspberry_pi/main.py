import os
import sys
import time
import signal
import logging
import serial
import RPi.GPIO as GPIO
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui.gui import RelayControlApp, MenuDialog
from gui.languages import LANGUAGES
import re

# ========== CONFIG & CONSTANTS ==========
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"error_log_{datetime.now().strftime('%Y-%m-%d')}.txt")
logging.basicConfig(
    filename=log_filename,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

arduino_ports = [
    '/dev/ttyACM0',
    '/dev/ttyACM1',
    '/dev/ttyACM2',
    '/dev/ttyACM3'
]

NUM_STATIONS = 4
config_file = "config.txt"
target_weight = 500.0
time_limit = 3000
scale_calibrations = []

# Protocol bytes
REQUEST_TARGET_WEIGHT = b'\x01'
REQUEST_CALIBRATION = b'\x02'
REQUEST_TIME_LIMIT = b'\x03'
CURRENT_WEIGHT = b'\x04'
RESET_CALIBRATION = b'\x05'
TARE_SCALE = b'\x09'
RELAY_DEACTIVATED = b'\xFA'
TARGET_WEIGHT = b'\x08'
VERBOSE_DEBUG = b'\xFE'
BEGIN_FILL = b'\x10'
CALIBRATION_STEP_DONE = b'\x12'
CALIBRATION_CONTINUE = b'\x13'
CALIBRATION_WEIGHT = b'\x14'
E_STOP_ACTIVATED = b'\xEE'
FILL_TIME = b'\x15'
FINAL_WEIGHT = b'\x11'
GET_ID = b'\xA0'
STOP = b'\xFD'
CONFIRM_ID = b'\xA1'
RESET_HANDSHAKE = b'\xB0'

# GPIO pins
UP_BUTTON_PIN = 5
DOWN_BUTTON_PIN = 6
SELECT_BUTTON_PIN = 16
E_STOP_PIN = 23
BUZZER_PIN = 26
RELAY_POWER_PIN = 17

# ========== GLOBALS ==========
E_STOP = False
PREV_E_STOP_STATE = GPIO.HIGH
FILL_LOCKED = False
last_fill_time = None
last_final_weight = None
fill_time_limit_reached = False
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
arduinos = [None] * NUM_STATIONS

# ========== UTILITY FUNCTIONS ==========

def log_uncaught_exceptions(exctype, value, tb):
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))
    print("Uncaught exception:", value)

sys.excepthook = log_uncaught_exceptions

def load_scale_calibrations():
    """Load scale calibration values from config.txt into the global scale_calibrations list."""
    global scale_calibrations
    calibrations = [1.0] * NUM_STATIONS
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, "r") as file:
            for line in file:
                if line.startswith("station") and "_calibration=" in line:
                    key, value = line.strip().split("=")
                    station_num = int(key.replace("station", "").replace("_calibration", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        calibrations[station_num - 1] = float(value)
    except FileNotFoundError:
        logging.error(f"{config_file} not found. Using default calibration values.")
    except Exception as e:
        logging.error(f"Error reading {config_file}: {e}")
    scale_calibrations = calibrations
    print(f"Loaded scale calibration values: {scale_calibrations}")

def load_station_enabled(config_path, num_stations=4):
    enabled = [False] * num_stations
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                for i in range(num_stations):
                    key = f"station{i+1}_enabled="
                    if line.startswith(key):
                        value = line.split("=")[1].strip().lower()
                        enabled[i] = value == "true"
                        print(f"[DEBUG] Found {key}{value} -> enabled[{i}] = {enabled[i]}")
    except Exception as e:
        print(f"Error reading station_enabled from config: {e}")
    print(f"[DEBUG] Final enabled list: {enabled}")
    return enabled

def load_station_serials():
    serials = [None] * NUM_STATIONS
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, "r") as file:
            for line in file:
                if line.startswith("station") and "_serial=" in line:
                    key, value = line.strip().split("=")
                    station_num = int(key.replace("station", "").replace("_serial", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        serials[station_num - 1] = value
    except Exception as e:
        logging.error(f"Error reading serials from config: {e}")
    return serials

def clear_serial_buffer(arduino):
    """Read and discard all available bytes from the Arduino serial buffer."""
    while arduino.in_waiting > 0:
        arduino.read(arduino.in_waiting)

# ========== GPIO FUNCTIONS ==========

def setup_gpio():
    try:
        GPIO.setwarnings(False)
        GPIO.cleanup()
        print('setting up GPIO')
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(E_STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.setup(RELAY_POWER_PIN, GPIO.OUT)
        print('GPIO setup complete')
    except Exception as e:
        logging.error(f"Error in setup_gpio: {e}")

def ping_buzzer(duration=0.05):
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def ping_buzzer_invalid():
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    time.sleep(0.05)
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

# ========== SESSION/DATA LOGGING ==========

def log_final_weight(station_index, final_weight):
    today = datetime.now().strftime("%Y-%m-%d")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"material_log_{today}.txt")
    with open(log_file, "a") as f:
        f.write(f"{datetime.now().isoformat()} session={SESSION_ID} station={station_index+1} weight={final_weight}\n")

# ========== ARDUINO COMMUNICATION ==========

def startup():
    global arduinos
    arduinos = [None] * NUM_STATIONS
    print("App initialized, contacting Arduinos...")
    station_serials = load_station_serials()

    for port in arduino_ports:
        try:
            arduino = serial.Serial(port, 9600, timeout=0.5)
            arduino.reset_input_buffer()
            print(f"Trying port {port}...")

            arduino.write(RESET_HANDSHAKE)
            arduino.flush()
            print(f"Sent RESET HANDSHAKE to {port}")

            arduino.write(b'PMID')
            arduino.flush()
            print(f"Sent 'PMID' handshake to {port}")

            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    print(f"Received from {port}: {repr(line)}")
                    match = re.match(r"<SERIAL:([A-Za-z0-9\-]+)>", line)
                    if match:
                        station_serial_number = match.group(1)
                        print(f"Station serial {station_serial_number} detected on {port}")
                        break
                time.sleep(0.1)
            if station_serial_number is None or station_serial_number not in station_serials:
                print(f"No recognized station detected on port {port}, skipping...")
                arduino.close()
                continue

            station_index = station_serials.index(station_serial_number)

            arduino.write(CONFIRM_ID)
            arduino.flush()
            print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

            got_request = False
            for _ in range(40):
                if arduino.in_waiting > 0:
                    req = arduino.read(1)
                    if req == REQUEST_CALIBRATION:
                        print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                        arduino.write(REQUEST_CALIBRATION)
                        arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                        got_request = True
                        break
                    else:
                        arduino.reset_input_buffer()
                time.sleep(0.1)
            if not got_request:
                print(f"Station {station_index+1}: Did not receive calibration request, skipping.")
                arduino.close()
                continue

            arduinos[station_index] = arduino
            print(f"Station {station_index+1} on {port} initialized and ready.")

        except serial.SerialException:
            print(f"No station detected on port {port}, skipping...")
        except Exception as e:
            print(f"Error initializing Arduino on {port}: {e}")
            logging.error(f"Error initializing Arduino on {port}: {e}")

def reconnect_arduino(station_index, port):
    print(f"reconnect_arduino called for {port}")
    try:
        if arduinos[station_index]:
            try:
                arduinos[station_index].close()
            except Exception:
                pass
            arduinos[station_index] = None

        arduino = serial.Serial(port, 9600, timeout=0.5)
        arduino.reset_input_buffer()
        time.sleep(1)

        arduino.write(RESET_HANDSHAKE)
        arduino.flush()
        print(f"Sent RESET_HANDSHAKE to {port}")
        time.sleep(0.5)

        arduino.write(b'PMID')
        arduino.flush()
        print(f"Sent 'PMID' handshake to {port}")

        station_serials = load_station_serials()
        station_serial_number = None
        for _ in range(60):
            if arduino.in_waiting > 0:
                line = arduino.read_until(b'\n').decode(errors='replace').strip()
                print(f"Received from {port}: {repr(line)}")
                match = re.match(r"<SERIAL:([A-Za-z0-9\-]+)>", line)
                if match:
                    station_serial_number = match.group(1)
                    print(f"Station serial {station_serial_number} detected on {port}")
                    break
            time.sleep(0.1)
        if station_serial_number is None or station_serial_number not in station_serials:
            print(f"No recognized station detected on port {port}, skipping...")
            arduino.close()
            return False

        station_index = station_serials.index(station_serial_number)

        arduino.write(CONFIRM_ID)
        arduino.flush()
        print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

        got_request = False
        for _ in range(40):
            if arduino.in_waiting > 0:
                req = arduino.read(1)
                if req == REQUEST_CALIBRATION:
                    print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                    arduino.write(REQUEST_CALIBRATION)
                    arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                    got_request = True
                    break
                else:
                    arduino.reset_input_buffer()
            time.sleep(0.1)
        if not got_request:
            print(f"Station {station_index+1}: Did not receive calibration request, skipping.")
            arduino.close()
            return False

        arduinos[station_index - 1] = arduino
        print(f"Station {station_index+1} on {port} reconnected and ready.")
        return True

    except Exception as e:
        print(f"Error reconnecting Arduino on {port}: {e}")
        logging.error(f"Error reconnecting Arduino on {port}: {e}")
        return False

def try_connect_station(station_index):
    port = arduino_ports[station_index]
    print(f"Attempting to (re)connect to station {station_index+1} on port {port}...")
    try:
        success = reconnect_arduino(station_index, port)
        if success:
            station_enabled[station_index] = True
            return True
        else:
            return False
    except Exception as e:
        print(f"Error in try_connect_station: {e}")
        return False

def poll_hardware(app):
    global E_STOP, FILL_LOCKED
    try:
        estop_pressed = GPIO.input(E_STOP_PIN) == GPIO.LOW

        # Handle E-STOP state change
        if estop_pressed and not E_STOP:
            print("E-STOP pressed")
            E_STOP = True
            FILL_LOCKED = True
            app.overlay_widget.show_overlay(
                f"<span style='font-size:80px; font-weight:bold;'>E-STOP</span><br>"
                f"<span style='font-size:40px;'>Emergency Stop Activated</span>",
                color="#CD0A0A"
            )
            for arduino in arduinos:
                if arduino:
                    arduino.write(E_STOP_ACTIVATED)
                    arduino.flush()
        elif not estop_pressed and E_STOP:
            print("E-STOP released")
            E_STOP = False
            FILL_LOCKED = False
            app.overlay_widget.hide_overlay()

        for station_index, arduino in enumerate(arduinos):
            if arduino is None or not station_enabled[station_index]:
                continue
            try:
                if E_STOP:
                    while arduino.in_waiting > 0:
                        arduino.read(arduino.in_waiting)
                    continue

                while arduino.in_waiting > 0:
                    message_type = arduino.read(1)
                    if message_type == REQUEST_TARGET_WEIGHT:
                        if FILL_LOCKED:
                            print(f"Station {station_index+1}: Fill locked, sending STOP_FILL")
                            arduino.write(STOP)
                        else:
                            arduino.write(TARGET_WEIGHT)
                            arduino.write(f"{target_weight}\n".encode('utf-8'))
                    elif message_type == REQUEST_CALIBRATION:
                        print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                        arduino.write(REQUEST_CALIBRATION)
                        arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                    elif message_type == REQUEST_TIME_LIMIT:
                        print(f"Station {station_index+1}: REQUEST_TIME_LIMIT")
                        arduino.write(REQUEST_TIME_LIMIT)
                        arduino.write(f"{time_limit}\n".encode('utf-8'))
                    elif message_type == CURRENT_WEIGHT:
                        current_weight = arduino.readline().decode('utf-8').strip()
                        try:
                            weight = float(current_weight)
                            if weight < 0:
                                weight = 0.0
                            app.update_station_weight(station_index, weight)
                        except Exception as e:
                            logging.error(f"Invalid weight value for station {station_index}: {current_weight} ({e})")
                            app.update_station_weight(station_index, 0.0)
                    elif message_type == FINAL_WEIGHT:
                        final_weight = arduino.readline().decode('utf-8').strip()
                        print(f"Station {station_index+1}: Final weight: {final_weight}")
                        try:
                            grams = float(final_weight)
                            log_final_weight(station_index, grams)
                        except Exception as e:
                            print(f"Could not log final weight: {e}")
                        if hasattr(app, "update_station_final_weight"):
                            app.update_station_final_weight(station_index, final_weight)
                        else:
                            if hasattr(app, "station_widgets"):
                                widget = app.station_widgets[station_index]
                                if hasattr(widget, "set_final_weight"):
                                    widget.set_final_weight(final_weight)
                    elif message_type == FILL_TIME:
                        fill_time = arduino.readline().decode('utf-8').strip()
                        print(f"Station {station_index+1}: Fill time: {fill_time}")
                        if hasattr(app, "update_station_fill_time"):
                            app.update_station_fill_time(station_index, fill_time)
                        else:
                            if hasattr(app, "station_widgets"):
                                widget = app.station_widgets[station_index]
                                if hasattr(widget, "set_fill_time"):
                                    widget.set_fill_time(fill_time)
                    else:
                        if arduino.in_waiting > 0:
                            extra = arduino.readline().decode('utf-8', errors='replace').strip()
                            print(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
                        else:
                            print(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
                            app.refresh_ui()
            except serial.SerialException as e:
                print(f"Lost connection to Arduino {station_index+1}: {e}")
                port = arduino_ports[station_index]
                reconnect_arduino(station_index, port)
    except Exception as e:
        logging.error(f"Error in poll_hardware: {e}")
        print(f"Error in poll_hardware: {e}")

# ========== GUI/BUTTON HANDLING ==========

def handle_button_presses(app):
    try:
        dialog = getattr(app, "active_dialog", None)

        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"UP button pressed, dialog: {dialog}")
            while GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_prev()
            return

        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"DOWN button pressed, dialog: {dialog}")
            while GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_next()
            return

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"SELECT button pressed, dialog: {dialog}")
            while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.activate_selected()
            else:
                print('select button pressed on main screen, opening menu')
                if not app.menu_dialog or not app.menu_dialog.isVisible():
                    app.show_menu()
            return

    except Exception as e:
        logging.error(f"Error in handle_button_presses: {e}")
        print(f"Error in handle_button_presses: {e}")

# ========== MAIN ENTRY POINT ==========

def main():
    try:
        logging.info("Starting main application.")
        load_scale_calibrations()
        global station_enabled
        config_path = "config.txt"
        station_enabled = load_station_enabled(config_path)
        print(f"Loaded station_enabled: {station_enabled}")
        setup_gpio()

        app_qt = QApplication(sys.argv)
        app = RelayControlApp(station_enabled=station_enabled)
        app.set_calibrate = None  # Set if you have a calibrate_scale function

        app.target_weight = target_weight

        print('app initialized, contacting arduinos')

        for i, widget in enumerate(app.station_widgets):
            if station_enabled[i]:
                widget.set_weight(0, target_weight)

        GPIO.output(RELAY_POWER_PIN, GPIO.HIGH)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        timer = QTimer()
        timer.timeout.connect(lambda: poll_hardware(app))
        timer.start(35)

        button_timer = QTimer()
        button_timer.timeout.connect(lambda: handle_button_presses(app))
        button_timer.start(50)

        QTimer.singleShot(1000, startup)

        sys.exit(app_qt.exec())
    except KeyboardInterrupt:
        print("Program interrupted by user.")
        logging.info("Program interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        print("Shutting down...")
        logging.info("Shutting down and cleaning up GPIO.")
        GPIO.cleanup()

if __name__ == "__main__":
    main()