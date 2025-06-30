import os
import sys
import time
import signal
import logging
import serial
import RPi.GPIO as GPIO
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
from gui.gui import RelayControlApp, MenuDialog, StartupDialog, CalibrationDialog, SelectionDialog, InfoDialog
from gui.languages import LANGUAGES
import re
from app_config import ERROR_LOG_FILE, STATS_LOG_FILE, ERROR_LOG_DIR, STATS_LOG_DIR

# ========== CONFIG & CONSTANTS ==========
LOG_DIR = "logs/errors"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(ERROR_LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=ERROR_LOG_FILE,
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
BEGIN_AUTO_FILL = b'\x10'
SET_MANUAL_FILL = b'\x16'
BEGIN_SMART_FILL = b'\x17'
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
BUTTON_ERROR = b'\xE0'

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
last_fill_time = [None] * NUM_STATIONS
last_final_weight = [None] * NUM_STATIONS
fill_time_limit_reached = False
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
arduinos = [None] * NUM_STATIONS
DEBUG = True  # Set to False to disable debug prints
station_connected = [arduino is not None for arduino in arduinos]
serial_numbers = [arduino.serial_number if arduino else None for arduino in arduinos]
filling_mode = "AUTO"  # Default mode

# ========== MESSAGE HANDLERS ==========
def handle_request_target_weight(station_index, arduino, **ctx):
    try:
        if ctx['FILL_LOCKED']:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Fill locked, sending STOP_FILL")
            arduino.write(STOP)
        else:
            arduino.write(TARGET_WEIGHT)
            arduino.write(f"{ctx['target_weight']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_target_weight", exc_info=True)

def handle_request_calibration(station_index, arduino, **ctx):
    try:
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {ctx['scale_calibrations'][station_index]}")
        arduino.write(REQUEST_CALIBRATION)
        arduino.write(f"{ctx['scale_calibrations'][station_index]}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_calibration", exc_info=True)

def handle_request_time_limit(station_index, arduino, **ctx):
    try:
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: REQUEST_TIME_LIMIT")
        arduino.write(REQUEST_TIME_LIMIT)
        arduino.write(f"{ctx['time_limit']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_time_limit", exc_info=True)

def handle_current_weight(station_index, arduino, **ctx):
    try:
        weight_bytes = arduino.read(4)
        if len(weight_bytes) == 4:
            weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            if weight < 0:
                weight = 0.0
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "CalibrationDialog":
                ctx['active_dialog'].set_weight(station_index, weight)
            elif ctx['update_station_weight']:
                ctx['update_station_weight'](station_index, weight)
        else:
            logging.error(f"Station {station_index}: Incomplete weight bytes received: {weight_bytes!r}")
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "CalibrationDialog":
                ctx['active_dialog'].set_weight(station_index, 0.0)
            elif ctx['update_station_weight']:
                ctx['update_station_weight'](station_index, 0.0)
    except Exception as e:
        logging.error("Error in handle_current_weight", exc_info=True)

def handle_begin_auto_fill(station_index, arduino, **ctx):
    try:
        widgets = ctx['station_widgets']
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                widget.set_status("AUTO FILL RUNNING")
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: BEGIN_AUTO_FILL received, status set.")
    except Exception as e:
        logging.error("Error in handle_begin_auto_fill", exc_info=True)

def handle_begin_smart_fill(station_index, arduino, **ctx):
    try:
        widgets = ctx['station_widgets']
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                widget.set_status("SMART FILL RUNNING")
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: BEGIN_SMART_FILL received, status set.")
    except Exception as e:
        logging.error("Error in handle_begin_smart_fill", exc_info=True)

def handle_final_weight(station_index, arduino, **ctx):
    try:
        weight_bytes = arduino.read(4)
        if len(weight_bytes) == 4:
            final_weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            last_final_weight[station_index] = final_weight
            # Try to update status if fill time is also available
            fill_time = last_fill_time[station_index]
            if fill_time is not None:
                seconds = int(round(fill_time / 1000))
                status = f"Filled {final_weight}g in {seconds}s"
                widgets = ctx.get('station_widgets')
                if widgets:
                    widget = widgets[station_index]
                    if hasattr(widget, "set_status"):
                        widget.set_status(status)
                last_fill_time[station_index] = None  # Reset after use
                last_final_weight[station_index] = None
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Final weight: {final_weight}")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Incomplete final weight bytes: {weight_bytes!r}")
    except Exception as e:
        logging.error("Error in handle_final_weight", exc_info=True)

def handle_fill_time(station_index, arduino, **ctx):
    try:
        time_bytes = arduino.read(4)
        if len(time_bytes) == 4:
            fill_time = int.from_bytes(time_bytes, byteorder='little', signed=False)
            last_fill_time[station_index] = fill_time
            # Try to update status if final weight is also available
            final_weight = last_final_weight[station_index]
            if final_weight is not None:
                seconds = int(round(fill_time / 1000))
                status = f"Filled {final_weight}g in {seconds}s"
                widgets = ctx.get('station_widgets')
                if widgets:
                    widget = widgets[station_index]
                    if hasattr(widget, "set_status"):
                        widget.set_status(status)
                last_fill_time[station_index] = None  # Reset after use
                last_final_weight[station_index] = None
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Fill time: {fill_time} ms")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Incomplete fill time bytes: {time_bytes!r}")
    except Exception as e:
        logging.error("Error in handle_fill_time", exc_info=True)

def handle_unknown(station_index, arduino, message_type, **ctx):
    try:
        if arduino.in_waiting > 0:
            extra = arduino.readline().decode('utf-8', errors='replace').strip()
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
            if ctx['refresh_ui']:
                ctx['refresh_ui']()
    except Exception as e:
        logging.error("Error in handle_unknown", exc_info=True)
MESSAGE_HANDLERS = {
    REQUEST_TARGET_WEIGHT: handle_request_target_weight,
    REQUEST_CALIBRATION: handle_request_calibration,
    REQUEST_TIME_LIMIT: handle_request_time_limit,
    CURRENT_WEIGHT: handle_current_weight,
    BEGIN_AUTO_FILL: handle_begin_auto_fill,
    BEGIN_SMART_FILL: handle_begin_smart_fill,
    FINAL_WEIGHT: handle_final_weight,
    FILL_TIME: handle_fill_time,
}

# ========== UTILITY FUNCTIONS ==========

def log_uncaught_exceptions(exctype, value, tb):
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))
    if DEBUG:
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
    if DEBUG:
        print(f"Loaded scale calibration values: {scale_calibrations}")

def load_station_enabled(config_path):
    enabled = [False] * NUM_STATIONS
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                for i in range(NUM_STATIONS):
                    key = f"station{i+1}_enabled="
                    if line.startswith(key):
                        value = line.split("=")[1].strip().lower()
                        enabled[i] = value == "true"
                        if DEBUG:
                            print(f"[DEBUG] Found {key}{value} -> enabled[{i}] = {enabled[i]}")
    except Exception as e:
        if DEBUG:
            print(f"Error reading station_enabled from config: {e}")
    if DEBUG:
        print(f"[DEBUG] Final enabled list: {enabled}")
    return enabled

def save_station_enabled(config_path, station_enabled):
    try:
        with open(config_path, "r") as f:
            lines = f.readlines()
        with open(config_path, "w") as f:
            for line in lines:
                written = False
                for i in range(NUM_STATIONS):
                    key = f"station{i+1}_enabled="
                    if line.strip().startswith(key):
                        f.write(f"{key}{'true' if station_enabled[i] else 'false'}\n")
                        written = True
                        break
                if not written:
                    f.write(line)
    except Exception as e:
        if DEBUG:
            print(f"Error writing station_enabled to config: {e}")

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
        if DEBUG:
            print('setting up GPIO')
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(E_STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        GPIO.setup(RELAY_POWER_PIN, GPIO.OUT)
        if DEBUG:
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
    os.makedirs(STATS_LOG_DIR, exist_ok=True)
    with open(STATS_LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} session={SESSION_ID} station={station_index+1} weight={final_weight}\n")

# ========== STARTUP ==========

def startup(app, timer):
    global arduinos, scale_calibrations, station_enabled, station_serials

    if DEBUG:
        print("[DEBUG] === Startup sequence initiated ===")

    # ========== Load station serials and scale calibrations ==========
    if DEBUG:
        print("[DEBUG] Loading scale calibrations and station serials...")
    load_scale_calibrations()
    station_serials = load_station_serials()
    if DEBUG:
        print(f"[DEBUG] station_serials: {station_serials}")
        print(f"[DEBUG] scale_calibrations: {scale_calibrations}")

    # ========== Connect and Setup Arduinos ==========
    if DEBUG:
        print("[DEBUG] Connecting and setting up Arduinos...")
    station_connected = [False] * NUM_STATIONS
    arduinos = [None] * NUM_STATIONS

    for port in arduino_ports:
        try:
            arduino = serial.Serial(port, 9600, timeout=0.5)
            arduino.reset_input_buffer()
            if DEBUG:
                print(f"Trying port {port}...")

            arduino.write(RESET_HANDSHAKE)
            arduino.flush()
            if DEBUG:
                print(f"Sent RESET HANDSHAKE to {port}")

            arduino.write(b'PMID')
            arduino.flush()
            if DEBUG:
                print(f"Sent 'PMID' handshake to {port}")

            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    if DEBUG:
                        print(f"Received from {port}: {repr(line)}")
                    match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                    if match:
                        station_serial_number = match.group(1)
                        if DEBUG:
                            print(f"Station serial {station_serial_number} detected on {port}")
                        break
                time.sleep(0.1)
            if station_serial_number is None or station_serial_number not in station_serials:
                if DEBUG:
                    print(f"No recognized station detected on port {port}, skipping...")
                arduino.close()
                continue

            station_index = station_serials.index(station_serial_number)

            arduino.write(CONFIRM_ID)
            arduino.flush()
            if DEBUG:
                print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

            got_request = False
            for _ in range(40):
                if arduino.in_waiting > 0:
                    req = arduino.read(1)
                    if req == REQUEST_CALIBRATION:
                        if DEBUG:
                            print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                        arduino.write(REQUEST_CALIBRATION)
                        arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                        got_request = True
                        break
                    else:
                        arduino.reset_input_buffer()
                time.sleep(0.1)
            if not got_request:
                if DEBUG:
                    print(f"Station {station_index+1}: Did not receive calibration request, skipping.")
                arduino.close()
                continue

            arduinos[station_index] = arduino
            station_connected[station_index] = True
            if DEBUG:
                print(f"Station {station_index+1} on {port} initialized and ready.")

        except serial.SerialException:
            if DEBUG:
                print(f"No station detected on port {port}, skipping...")
        except Exception as e:
            if DEBUG:
                print(f"Error initializing Arduino on {port}: {e}")
            logging.error(f"Error initializing Arduino on {port}: {e}")

    # ========== Load enabled states ==========
    if DEBUG:
        print("[DEBUG] Loading enabled states...")
    station_enabled = load_station_enabled("config.txt")
    if DEBUG:
        print(f"[DEBUG] station_enabled: {station_enabled}")

    # ========== Check E-STOP state ==========
    if DEBUG:
        print("[DEBUG] Checking E-STOP state...")
    while GPIO.input(E_STOP_PIN) == GPIO.LOW:
        time.sleep(0.1)

    # ========== Step 1: Verify Stations ==========
    if DEBUG:
        print("[DEBUG] Step 1: Verify Stations dialog")
    dialog = StartupDialog("Are these the filling stations you are using?", parent=app)
    app.active_dialog = dialog
    dialog.showFullScreen()
    QApplication.processEvents()

    # Prepare station names, statuses, and colors
    station_names = [f"Station {i+1}" for i in range(NUM_STATIONS)]
    statuses = []
    for i in range(NUM_STATIONS):
        if station_enabled[i] and station_connected[i]:
            statuses.append("ENABLED & CONNECTED")
        elif station_enabled[i] and not station_connected[i]:
            statuses.append("ENABLED & DISCONNECTED")
        elif not station_enabled[i] and station_connected[i]:
            statuses.append("DISABLED & CONNECTED")
        else:
            statuses.append("DISABLED & DISCONNECTED")
    if DEBUG:
        print(f"[DEBUG] Station statuses: {statuses}")

    colors = getattr(app, "bg_colors", ["#444"] * NUM_STATIONS)

    # Show the verification dialog with current station info
    dialog.show_station_verification(station_names, statuses, colors, station_connected)
    QApplication.processEvents()

    if DEBUG:
        print("[DEBUG] Waiting for user to select YES/NO...")
    while dialog.result() == 0:
        QApplication.processEvents()
        time.sleep(0.01)

    result = dialog.result()
    # Always save the current station_enabled state before continuing
    save_station_enabled(config_file, station_enabled)
    if DEBUG:
        print(f"[DEBUG] Station verification dialog result: {result}")
    dialog.accept()
    app.active_dialog = None

    # YES selected: proceed to next step
    # ========== Step 2: Select Filling Mode ==========
    if DEBUG:
        print("[DEBUG] Step 2: Select Filling Mode dialog")
    filling_modes = [("AUTO", "AUTO"), ("MANUAL", "MANUAL"), ("SMART", "SMART")]
    filling_mode_dialog = SelectionDialog(
        options=filling_modes,
        parent=app,
        title="Select Filling Mode"
    )
    app.active_dialog = filling_mode_dialog
    result = filling_mode_dialog.exec()  # This blocks until the dialog is closed

    selected_index = filling_mode_dialog.selected_index
    filling_modes_list = ["AUTO", "MANUAL", "SMART"]
    app.filling_mode = filling_modes_list[selected_index]
    global filling_mode
    filling_mode = app.filling_mode  # Always sync global with app

    if DEBUG:
        print(f"[DEBUG] Filling mode selected: {app.filling_mode}")
    app.active_dialog = None

    # If MANUAL mode, show popup, send command, and exit startup
    if filling_mode == "MANUAL":
        MANUAL_FILL_START = b'\x20'
        for i, arduino in enumerate(arduinos):
            if arduino and station_enabled[i]:
                try:
                    arduino.write(MANUAL_FILL_START)
                    arduino.flush()
                    if DEBUG:
                        print(f"[DEBUG] Sent MANUAL_FILL_START to station {i+1}")
                except Exception as e:
                    if DEBUG:
                        print(f"[DEBUG] Failed to send MANUAL_FILL_START to station {i+1}: {e}")
        info = InfoDialog("MANUAL FILLING MODE", "Manual filling mode selected.<br>Startup complete.", app)
        info.setWindowModality(Qt.WindowModality.ApplicationModal)
        info.show()
        QTimer.singleShot(2000, info.accept)
        while info.result() == 0:
            QApplication.processEvents()
            time.sleep(0.01)
        return

    # ========== Step 3: Calibration Check ==========
    print("[DEBUG] Step 3: Calibration Check dialog - BEGIN")
    calib_dialog = CalibrationDialog(station_enabled, parent=app)
    calib_dialog.set_main_label("CALIBRATING")
    calib_dialog.set_sub_label("Clear all stations (including empty bottles), then press any button.")
    calib_dialog.set_bottom_label("")

    app.active_dialog = calib_dialog
    calib_dialog.show()
    QApplication.processEvents()

    print("[DEBUG] Waiting for first button press (empty stations)...")
    while calib_dialog.result() == 0:
        # arduino.Write(TARE_SCALE)
        QApplication.processEvents()
        time.sleep(0.01)
    print("[DEBUG] Step 3: Calibration Check dialog - END")

    # ========== Full Bottle Check ==========
    print("[DEBUG] Full Bottle Check - BEGIN")
    calib_dialog.set_sub_label("Place a full bottle in each active station, then press any button.")
    calib_dialog.set_bottom_label("")
    calib_dialog.show()
    QApplication.processEvents()

    print("[DEBUG] Waiting for full bottle check (live weight/color updates)...")

    while True:
        calib_dialog.done(0)
        calib_dialog.set_sub_label("Place a full bottle in each active station, then press any button.")
        calib_dialog.set_bottom_label("")
        calib_dialog.show()
        QApplication.processEvents()

        # Live update loop: update colors and weights until a button is pressed
        while calib_dialog.result() == 0:
            for i in range(NUM_STATIONS):
                if station_enabled[i]:
                    try:
                        weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                        weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                        # Set color based on weight
                        if 375 <= weight <= 425 or 715 <= weight <= 765:
                            # In valid range: green
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22; border-radius: 8px;")
                        else:
                            # Out of range: red
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
                    except Exception:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
            QApplication.processEvents()
            time.sleep(0.05)

        # After button press, gather weights and check ranges
        weights = []
        failed_stations = []
        for i in range(NUM_STATIONS):
            if station_enabled[i]:
                try:
                    weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                    weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                    weights.append((i, weight))
                    # Set color again for feedback
                    if 375 <= weight <= 425 or 725 <= weight <= 775:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22; border-radius: 8px;")
                    else:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
                        failed_stations.append(str(i + 1))
                except Exception:
                    failed_stations.append(str(i + 1))

        in_first_range = [i for i, w in weights if 375 <= w <= 425]
        in_second_range = [i for i, w in weights if 715 <= w <= 765]

        if len(in_first_range) == len(weights):
            failed_stations = []
            app.target_weight = 400
        elif len(in_second_range) == len(weights):
            failed_stations = []
            app.target_weight = 750
        else:
            failed_stations = [
                str(i + 1)
                for i, w in weights
                if not (375 <= w <= 425 or 725 <= w <= 775)
            ]
            if not failed_stations and len(weights) > 0:
                failed_stations = [str(i + 1) for i, _ in weights]

        if failed_stations:
            calib_dialog.set_bottom_label(
                "ERROR ON STATION" +
                ("S" if len(failed_stations) > 1 else "") +
                " " + ", ".join(failed_stations) +
                "<br>ALL STATIONS MUST USE THE SAME SIZE<br>Press any button to try again."
            )
            calib_dialog.done(0)
            continue  # Repeat the loop for another attempt
        else:
            print("[DEBUG] Full Bottle Check - END")
            # Properly close the dialog before moving on
            calib_dialog.accept()
            break  # All stations OK, continue to next step

# ========== Step 4: Empty Bottle Check ==========
    calib_dialog.set_sub_label("Place an empty bottle in each active station")
    calib_dialog.set_bottom_label("Press any button to continue")
    QApplication.processEvents()

    print("[DEBUG] Waiting for empty bottle check...")
    while True:
        calib_dialog.set_sub_label("Place an empty bottle in each active station")
        calib_dialog.set_bottom_label("Press any button to continue")
        calib_dialog.show()
        QApplication.processEvents()

        # Live update loop: update colors and weights until a button is pressed
        while calib_dialog.result() == 0:
            for i in range(NUM_STATIONS):
                if station_enabled[i]:
                    try:
                        weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                        weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                        # Set color based on weight
                        if app.target_weight == 400:
                            in_range = 18 <= weight <= 22
                        elif app.target_weight == 750:
                            in_range = 29 <= weight <= 33
                        else:
                            in_range = False
                        if in_range:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22; border-radius: 8px;")
                        else:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
                    except Exception:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
            QApplication.processEvents()
            time.sleep(0.05)

        # After button press, check weights for each active station
        failed_stations = []
        for i in range(NUM_STATIONS):
            if station_enabled[i]:
                try:
                    weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                    weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                    # Set color again for feedback
                    if app.target_weight == 400:
                        in_range = 18 <= weight <= 22
                    elif app.target_weight == 750:
                        in_range = 29 <= weight <= 33
                    else:
                        in_range = False
                    if in_range:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22; border-radius: 8px;")
                    else:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
                        failed_stations.append(str(i + 1))
                except Exception:
                    calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222; border-radius: 8px;")
                    failed_stations.append(str(i + 1))
        if not failed_stations:
            print("[DEBUG] Empty Bottle Check - END")
            calib_dialog.accept()
            break  # All stations OK, continue to next step
        else:
            calib_dialog.set_bottom_label(
                "ERROR ON STATION" +
                ("S" if len(failed_stations) > 1 else "") +
                " " + ", ".join(failed_stations)
            )
            # Beep buzzer three times
            for _ in range(3):
                ping_buzzer()
                time.sleep(0.15)
            calib_dialog.set_bottom_label("Press any button to continue")
            calib_dialog.done(0)  # Reset dialog so next button press will close it again
            continue

    # ========== Final Setup ==========
    if DEBUG:
        print("[DEBUG] Entering Final Setup after empty bottle check")
    button_error_counts = [0] * NUM_STATIONS
    faulty_stations = set()
    timeout = 6  # seconds
    start_time = time.time()

    # Show the dialog for button check
    calib_dialog.set_main_label("BUTTON CHECK")
    calib_dialog.set_sub_label("Checking station buttons for faults...")
    calib_dialog.set_bottom_label(f"Checking... {timeout} seconds remaining")
    for i in range(NUM_STATIONS):
        if station_enabled[i]:
            calib_dialog.weight_labels[i].setText(f"STATION {i+1}: OK")
            calib_dialog.weight_labels[i].setStyleSheet(
                "color: #fff; background: #228B22; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
            )
            calib_dialog.weight_labels[i].setFixedWidth(180)
        else:
            calib_dialog.weight_labels[i].setText(f"STATION {i+1}: DISABLED")
            calib_dialog.weight_labels[i].setStyleSheet(
                "color: #fff; background: #888; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
            )
            calib_dialog.weight_labels[i].setFixedWidth(180)
    calib_dialog.resize(1200, 400)  # Match the size used in full/empty bottle checks
    calib_dialog.show()
    QApplication.processEvents()

    last_seconds_left = timeout
    while True:
        elapsed = time.time() - start_time
        seconds_left = max(0, int(timeout - elapsed))
        print(f"[DEBUG] Final setup loop: elapsed={elapsed:.2f}s, seconds_left={seconds_left}")
        # Only update label if seconds_left changed
        if seconds_left != last_seconds_left:
            print(f"[DEBUG] Updating bottom label: Checking... {seconds_left} seconds remaining")
            calib_dialog.set_bottom_label(f"Checking... {seconds_left} seconds remaining")
            last_seconds_left = seconds_left
            QApplication.processEvents()

        for i in range(NUM_STATIONS):
            # Only check stations that are enabled and not already faulty
            if station_enabled[i] and i not in faulty_stations and arduinos[i] and arduinos[i].in_waiting > 0:
                print(f"[DEBUG] Checking station {i+1}: enabled={station_enabled[i]}, arduino={arduinos[i] is not None}")
                print(f"[DEBUG] Station {i+1} has {arduinos[i].in_waiting} bytes waiting")
                try:
                    byte = arduinos[i].read(1)
                    print(f"[DEBUG] Read byte from station {i+1}: {byte}")
                    if byte == BUTTON_ERROR:
                        button_error_counts[i] += 1
                        print(f"[DEBUG] BUTTON_ERROR for station {i+1}, count={button_error_counts[i]}")
                        if button_error_counts[i] >= 2 and i not in faulty_stations:
                            faulty_stations.add(i)
                            calib_dialog.weight_labels[i].setText(f"STATION {i+1}: BUTTON ERROR")
                            calib_dialog.weight_labels[i].setStyleSheet(
                                "color: #fff; background: #B22222; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                            )
                            calib_dialog.weight_labels[i].setFixedWidth(180)
                            calib_dialog.set_sub_label(f"STATION {i+1} button is malfunctioning.")
                            calib_dialog.set_bottom_label(f"For your safety, station {i+1} has been disabled<br>Checking... {seconds_left} seconds remaining")
                            station_enabled[i] = False
                            save_station_enabled(config_file, station_enabled)
                            QApplication.processEvents()
                    elif byte == CURRENT_WEIGHT:
                        # Discard the next 4 bytes (the weight value)
                        extra = arduinos[i].read(4)
                        print(f"[DEBUG] Discarded 4 bytes after CURRENT_WEIGHT: {extra}")
                    else:
                        print(f"[DEBUG] Unhandled byte from station {i+1}: {byte}")
                except Exception as e:
                    print(f"[DEBUG] Exception in button error check for station {i+1}: {e}")

        # Update all labels for stations that are still OK
        for i in range(NUM_STATIONS):
            if station_enabled[i] and i not in faulty_stations:
                calib_dialog.weight_labels[i].setText(f"STATION {i+1}: OK")
                calib_dialog.weight_labels[i].setStyleSheet(
                    "color: #fff; background: #228B22; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                )
                calib_dialog.weight_labels[i].setFixedWidth(180)
            elif not station_enabled[i]:
                calib_dialog.weight_labels[i].setText(f"STATION {i+1}: DISABLED")
                calib_dialog.weight_labels[i].setStyleSheet(
                    "color: #fff; background: #888; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                )
                calib_dialog.weight_labels[i].setFixedWidth(180)
        QApplication.processEvents()
        time.sleep(0.05)
        if elapsed >= timeout:
            print(f"[DEBUG] Timeout reached, breaking loop")
            break

    if DEBUG:
        print("[DEBUG] Final Setup complete, showing final calibration message")
    # Show final message
    if not faulty_stations:
        calib_dialog.set_sub_label("Calibration complete.")
    else:
        calib_dialog.set_sub_label("Some stations disabled due to button error.")
    calib_dialog.set_bottom_label("Press any button to continue.")
    QApplication.processEvents()

    if DEBUG:
        print("[DEBUG] Waiting for user to acknowledge calibration complete")
    # Wait for user to acknowledge (handled by handle_button_presses)
    while calib_dialog.result() == 0:
        QApplication.processEvents()
        time.sleep(0.01)

    if DEBUG:
        print("[DEBUG] Calibration dialog accepted, finishing calibration setup")
    app.active_dialog = None
    calib_dialog.accept()

    # ========== If MANUAL mode, send MANUAL_FILL_START to all connected stations ==========
    if getattr(app, "filling_mode", "AUTO") == "MANUAL":
        MANUAL_FILL_START = b'\x20'
        for i, arduino in enumerate(arduinos):
            if arduino and station_enabled[i]:
                try:
                    arduino.write(MANUAL_FILL_START)
                    arduino.flush()
                    if DEBUG:
                        print(f"[DEBUG] Sent MANUAL_FILL_START to station {i+1}")
                except Exception as e:
                    if DEBUG:
                        print(f"[DEBUG] Failed to send MANUAL_FILL_START to station {i+1}: {e}")

def reconnect_arduino(station_index, port):
    if DEBUG:
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
        if DEBUG:
            print(f"Sent RESET_HANDSHAKE to {port}")
        time.sleep(0.5)

        arduino.write(b'PMID')
        arduino.flush()
        if DEBUG:
            print(f"Sent 'PMID' handshake to {port}")

        station_serials = load_station_serials()
        station_serial_number = None
        for _ in range(60):
            if arduino.in_waiting > 0:
                line = arduino.read_until(b'\n').decode(errors='replace').strip()
                if DEBUG:
                    print(f"Received from {port}: {repr(line)}")
                match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                if match:
                    station_serial_number = match.group(1)
                    if DEBUG:
                        print(f"Station serial {station_serial_number} detected on {port}")
                    break
            time.sleep(0.1)
        if station_serial_number is None or station_serial_number not in station_serials:
            if DEBUG:
                print(f"No recognized station detected on port {port}, skipping...")
            arduino.close()
            return False

        station_index = station_serials.index(station_serial_number)

        arduino.write(CONFIRM_ID)
        arduino.flush()
        if DEBUG:
            print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

        got_request = False
        for _ in range(40):
            if arduino.in_waiting > 0:
                req = arduino.read(1)
                if req == REQUEST_CALIBRATION:
                    if DEBUG:
                        print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                    arduino.write(REQUEST_CALIBRATION)
                    arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                    got_request = True
                    break
                else:
                    arduino.reset_input_buffer()
            time.sleep(0.1)
        if not got_request:
            if DEBUG:
                print(f"Station {station_index+1}: Did not receive calibration request, skipping.")
            arduino.close()
            return False

        arduinos[station_index - 1] = arduino
        if DEBUG:
            print(f"Station {station_index+1} on {port} reconnected and ready.")
        return True

    except Exception as e:
        if DEBUG:
            print(f"Error reconnecting Arduino on {port}: {e}")
        logging.error(f"Error reconnecting Arduino on {port}: {e}")
        return False

def try_connect_station(station_index):
    port = arduino_ports[station_index]
    if DEBUG:
        print(f"Attempting to (re)connect to station {station_index+1} on port {port}...")
    try:
        success = reconnect_arduino(station_index, port)
        if success:
            station_enabled[station_index] = True
            return True
        else:
            return False
    except Exception as e:
        if DEBUG:
            print(f"Error in try_connect_station: {e}")
        return False

def poll_hardware(app):
    global E_STOP, FILL_LOCKED
    try:
        # Localize frequently accessed attributes
        station_widgets = getattr(app, "station_widgets", None)
        active_dialog = getattr(app, "active_dialog", None)
        filling_mode = getattr(app, "filling_mode", "AUTO")
        overlay_widget = getattr(app, "overlay_widget", None)
        refresh_ui = getattr(app, "refresh_ui", None)
        update_station_weight = getattr(app, "update_station_weight", None)

        estop_pressed = GPIO.input(E_STOP_PIN) == GPIO.LOW

        # Handle E-STOP state change
        if estop_pressed and not E_STOP:
            if DEBUG:
                print("E-STOP pressed")
            E_STOP = True
            FILL_LOCKED = True
            if active_dialog is not None:
                try:
                    active_dialog.reject()
                except Exception as e:
                    logging.error(f"Error rejecting active dialog: {e}")
                app.active_dialog = None

            if overlay_widget:
                overlay_widget.show_overlay(
                    f"<span style='font-size:80px; font-weight:bold;'>E-STOP</span><br>"
                    f"<span style='font-size:40px;'>Emergency Stop Activated</span>",
                    color="#CD0A0A"
                )
            for arduino in arduinos:
                if arduino:
                    arduino.write(E_STOP_ACTIVATED)
                    arduino.flush()
        elif not estop_pressed and E_STOP:
            if DEBUG:
                print("E-STOP released")
            E_STOP = False
            FILL_LOCKED = False
            if overlay_widget:
                overlay_widget.hide_overlay()

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
                    handler = MESSAGE_HANDLERS.get(message_type)
                    ctx = {
                        'FILL_LOCKED': FILL_LOCKED,
                        'DEBUG': DEBUG,
                        'target_weight': target_weight,
                        'scale_calibrations': scale_calibrations,
                        'time_limit': time_limit,
                        'active_dialog': active_dialog,
                        'update_station_weight': update_station_weight,
                        'station_widgets': station_widgets,
                        'refresh_ui': refresh_ui,
                    }
                    if handler:
                        handler(station_index, arduino, **ctx)
                    else:
                        handle_unknown(station_index, arduino, message_type, **ctx)
            except serial.SerialException as e:
                if DEBUG:
                    print(f"Lost connection to Arduino {station_index+1}: {e}")
                port = arduino_ports[station_index]
                reconnect_arduino(station_index, port)
    except Exception as e:
                logging.error(f"Error in poll_hardware: {e}")
                if DEBUG:
                    print(f"Error in poll_hardware: {e}")

# ========== GUI/BUTTON HANDLING ==========

def handle_button_presses(app):
    try:
        dialog = getattr(app, "active_dialog", None)

        # UP BUTTON
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            if DEBUG:
                print(f"UP button pressed, dialog: {dialog}")
            if dialog is not None and hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("up")
            while GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_prev()
                if hasattr(dialog, "set_arrow_inactive"):
                    dialog.set_arrow_inactive("up")
            return

        # DOWN BUTTON
        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            if DEBUG:
                print(f"DOWN button pressed, dialog: {dialog}")
            if dialog is not None and hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("down")
            while GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_next()
                if hasattr(dialog, "set_arrow_inactive"):
                    dialog.set_arrow_inactive("down")
            return

        # SELECT BUTTON
        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            if DEBUG:
                print(f"SELECT button pressed, dialog: {dialog}")
            while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                try:
                    dialog.activate_selected()
                except Exception as e:
                    logging.error("Error in dialog.activate_selected()", exc_info=True)
                    if DEBUG:
                        print(f"Error in dialog.activate_selected(): {e}")
            else:
                if DEBUG:
                    print('select button pressed on main screen, opening menu')
                if not app.menu_dialog or not app.menu_dialog.isVisible():
                    app.show_menu()
            return

    except Exception as e:
        logging.error("Error in handle_button_presses", exc_info=True)
        if DEBUG:
            print(f"Error in handle_button_presses: {e}")

# ========== MAIN ENTRY POINT ==========

def main():
    try:
        logging.info("Starting main application.")
        load_scale_calibrations()
        global station_enabled
        config_path = "config.txt"
        station_enabled = load_station_enabled(config_path)
        if DEBUG:
            print(f"Loaded station_enabled: {station_enabled}")
        setup_gpio()

        app_qt = QApplication(sys.argv)
        app = RelayControlApp(station_enabled=station_enabled)
        app.set_calibrate = None  # Set if you have a calibrate_scale function

        app.target_weight = target_weight

        if DEBUG:
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

        QTimer.singleShot(1000, lambda: startup(app, timer))

        sys.exit(app_qt.exec())
    except KeyboardInterrupt:
        if DEBUG:
            print("Program interrupted by user.")
        logging.info("Program interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        if DEBUG:
            print("Shutting down...")
        logging.info("Shutting down and cleaning up GPIO.")
        GPIO.cleanup()

if __name__ == "__main__":
    main()