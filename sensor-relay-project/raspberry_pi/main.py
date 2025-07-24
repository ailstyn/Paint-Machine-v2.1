import os
import logging

from app_config import ERROR_LOG_FILE, ERROR_LOG_DIR

os.makedirs(ERROR_LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print(f"Logging to: {ERROR_LOG_FILE}")

# Test log entry
logging.error("Test error log entry: If you see this, logging is working.")

# Now import the rest
import sys
import time
import signal
import serial
import RPi.GPIO as GPIO
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
from gui.gui import RelayControlApp, MenuDialog, StartupDialog, CalibrationDialog, SelectionDialog, InfoDialog
from gui.languages import LANGUAGES
import re
from app_config import STATS_LOG_FILE, STATS_LOG_DIR

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
MAX_WEIGHT_WARNING = b'\xE1'
MAX_WEIGHT_END = b'\xE2'  # <-- Add this new protocol byte
EXIT_MANUAL_END = b'\x22'  # Or import from your protocol/constants file

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
DEBUG = False  # Set to False to disable debug prints
station_connected = [arduino is not None for arduino in arduinos]
serial_numbers = [arduino.serial_number if arduino else None for arduino in arduinos]
filling_mode = "AUTO"  # Default mode
station_max_weight_error = [False] * NUM_STATIONS

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
            #if weight < 0:
             #    weight = 0.0
            widgets = ctx.get('station_widgets')
            if widgets:
                widget = widgets[station_index]
                # Set color based on max weight error state
                if station_max_weight_error[station_index]:
                    widget.weight_label.setStyleSheet("color: #FF2222;")  # Red
                else:
                    widget.weight_label.setStyleSheet("color: #fff;")     # Normal
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
        app = ctx.get('app')
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                if app:
                    widget.set_status(app.tr("AUTO FILL RUNNING"))
                else:
                    widget.set_status("AUTO FILL RUNNING")
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: BEGIN_AUTO_FILL received, status set.")
    except Exception as e:
        logging.error("Error in handle_begin_auto_fill", exc_info=True)

def handle_begin_smart_fill(station_index, arduino, **ctx):
    try:
        widgets = ctx['station_widgets']
        app = ctx.get('app')
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                if app:
                    widget.set_status(app.tr("SMART FILL RUNNING"))
                else:
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
                logging.error(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
            else:
                logging.error(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
            if ctx['refresh_ui']:
                ctx['refresh_ui']()
    except Exception as e:
        logging.error("Error in handle_unknown", exc_info=True)

def handle_max_weight_warning(station_index, arduino, **ctx):
    widgets = ctx.get('station_widgets')
    app = ctx.get('app')
    station_max_weight_error[station_index] = True
    if widgets:
        widget = widgets[station_index]
        if hasattr(widget, "set_status"):
            if app:
                widget.set_status(f"<b>{app.tr('MAX WEIGHT EXCEEDED')}</b>", color="#FF2222", flashing=True)
            else:
                widget.set_status("<b>MAX WEIGHT EXCEEDED</b>", color="#FF2222", flashing=True)
    if DEBUG:
        print(f"[WARNING] Station {station_index+1}: MAX_WEIGHT_WARNING received")

def handle_max_weight_end(station_index, arduino, **ctx):
    widgets = ctx.get('station_widgets')
    station_max_weight_error[station_index] = False
    if widgets:
        widget = widgets[station_index]
        if hasattr(widget, "clear_status"):
            widget.clear_status()
        elif hasattr(widget, "set_status"):
            widget.set_status("")  # Fallback: clear status text
    if DEBUG:
        print(f"[INFO] Station {station_index+1}: MAX_WEIGHT_END received, warning cleared.")

MESSAGE_HANDLERS = {
    REQUEST_TARGET_WEIGHT: handle_request_target_weight,
    REQUEST_CALIBRATION: handle_request_calibration,
    REQUEST_TIME_LIMIT: handle_request_time_limit,
    CURRENT_WEIGHT: handle_current_weight,
    BEGIN_AUTO_FILL: handle_begin_auto_fill,
    BEGIN_SMART_FILL: handle_begin_smart_fill,
    FINAL_WEIGHT: handle_final_weight,
    FILL_TIME: handle_fill_time,
    MAX_WEIGHT_WARNING: handle_max_weight_warning,
    MAX_WEIGHT_END: handle_max_weight_end,  # <-- Register the new handler
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

def run_startup_sequence(app_qt):
    """
    Run all startup dialogs and calibration logic before showing the main window.
    Returns a dict with all state needed to create the main window.
    """
    # Local translation function (no-op, replace with real translation if needed)
    tr = lambda k: k

    # Setup GPIO, load configs, connect arduinos, etc.
    setup_gpio()
    load_scale_calibrations()
    config_path = "config.txt"
    station_enabled = load_station_enabled(config_path)
    station_serials = load_station_serials()

    # Fix: define these at the top
    scale_calibrations_local = list(scale_calibrations)
    arduinos_local = [None] * NUM_STATIONS

    # Connect arduinos
    station_connected = [False] * NUM_STATIONS
    for port in arduino_ports:
        try:
            arduino = serial.Serial(port, 9600, timeout=0.5)
            arduino.reset_input_buffer()
            arduino.write(RESET_HANDSHAKE)
            arduino.flush()
            arduino.write(b'PMID')
            arduino.flush()
            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                    if match:
                        station_serial_number = match.group(1)
                        break
                time.sleep(0.1)
            if station_serial_number is None or station_serial_number not in station_serials:
                arduino.close()
                continue
            station_index = station_serials.index(station_serial_number)
            arduino.write(CONFIRM_ID)
            arduino.flush()
            got_request = False
            for _ in range(40):
                if arduino.in_waiting > 0:
                    req = arduino.read(1)
                    if req == REQUEST_CALIBRATION:
                        arduino.write(REQUEST_CALIBRATION)
                        arduino.write(f"{scale_calibrations_local[station_index]}\n".encode('utf-8'))
                        got_request = True
                        break
                    else:
                        arduino.reset_input_buffer()
                time.sleep(0.1)
            if not got_request:
                arduino.close()
                continue
            arduinos_local[station_index] = arduino
            station_connected[station_index] = True
        except Exception as e:
            logging.error(f"Error initializing Arduino on {port}: {e}")

    # Wait for E-STOP to be released
    while GPIO.input(E_STOP_PIN) == GPIO.LOW:
        time.sleep(0.1)

    # --- Step 1: Verify Stations ---
    dialog = StartupDialog(tr("Are these the filling stations you are using?"), parent=None)
    station_names = [tr("STATION") + f" {i+1}" for i in range(NUM_STATIONS)]
    statuses = []
    for i in range(NUM_STATIONS):
        if station_enabled[i] and station_connected[i]:
            statuses.append(tr("ENABLED") + " & " + tr("CONNECTED"))
        elif station_enabled[i] and not station_connected[i]:
            statuses.append(tr("ENABLED") + " & " + tr("DISCONNECTED"))
        elif not station_enabled[i] and station_connected[i]:
            statuses.append(tr("DISABLED") + " & " + tr("CONNECTED"))
        else:
            statuses.append(tr("DISABLED") + " & " + tr("DISCONNECTED"))
    colors = ["#444"] * NUM_STATIONS
    dialog.show_station_verification(station_names, statuses, colors, station_connected)
    dialog.selected_index = len(getattr(dialog, "selection_indices", [])) - 1
    dialog.show_station_verification(station_names, statuses, colors, station_connected)
    dialog.setModal(True)
    dialog.exec()
    save_station_enabled(config_file, station_enabled)

    # --- Step 2: Select Filling Mode ---
    filling_modes = [("AUTO", tr("AUTO")), ("MANUAL", tr("MANUAL")), ("SMART", tr("SMART"))]
    filling_mode_dialog = SelectionDialog(
        options=filling_modes,
        parent=None,
        title=tr("SET FILLING MODE")
    )
    filling_mode_dialog.setModal(True)
    filling_mode_dialog.exec()
    selected_index = filling_mode_dialog.selected_index
    filling_modes_list = ["AUTO", "MANUAL", "SMART"]
    filling_mode = filling_modes_list[selected_index]

    # If MANUAL mode, show popup, send command, and exit startup
    if filling_mode == "MANUAL":
        MANUAL_FILL_START = b'\x20'
        for i, arduino in enumerate(arduinos_local):
            if arduino and station_enabled[i]:
                try:
                    arduino.write(MANUAL_FILL_START)
                    arduino.flush()
                except Exception as e:
                    logging.error(f"Failed to send MANUAL_FILL_START to station {i+1}: {e}")
        info = InfoDialog(tr("MANUAL FILLING MODE"), tr("Manual filling mode selected.<br>Startup complete."), None)
        info.setWindowModality(Qt.WindowModality.ApplicationModal)
        info.exec()
        return {
            "station_enabled": station_enabled,
            "scale_calibrations": scale_calibrations_local,
            "target_weight": target_weight,
            "time_limit": time_limit,
            "filling_mode": filling_mode,
            "arduinos": arduinos_local,
        }

    # --- Step 3: Calibration Check (Remove Weight) ---
    calib_dialog = CalibrationDialog(station_enabled, parent=None)
    calib_dialog.set_main_label(tr("CALIBRATION_TITLE"))
    calib_dialog.set_sub_label(tr("CALIBRATION_REMOVE_WEIGHT"))
    calib_dialog.set_bottom_label("")
    calib_dialog.setModal(True)
    calib_dialog.resize(900, 500)
    calib_dialog.move(
        calib_dialog.screen().geometry().center() - calib_dialog.rect().center()
    )
    calib_dialog.exec()

    # --- Tare all enabled stations after user confirms remove weight ---
    for i, arduino in enumerate(arduinos_local):
        if arduino and station_enabled[i]:
            try:
                arduino.write(TARE_SCALE)
                arduino.flush()
            except Exception as e:
                logging.error(f"Failed to send TARE_SCALE to station {i+1}: {e}")

    # --- Step 4: Full Bottle Check (Live update loop) ---
    calib_dialog = CalibrationDialog(station_enabled, parent=None)
    calib_dialog.set_main_label(tr("CALIBRATION_TITLE"))
    calib_dialog.set_sub_label(tr("Place a full bottle in each active station, then press any button."))
    calib_dialog.set_bottom_label("")
    calib_dialog.setModal(True)
    calib_dialog.resize(900, 500)
    calib_dialog.move(
        calib_dialog.screen().geometry().center() - calib_dialog.rect().center()
    )
    calib_dialog.show()
    QApplication.processEvents()
    target_weight_local = 500.0
    while True:
        while calib_dialog.result() == 0:
            for i in range(NUM_STATIONS):
                if station_enabled[i]:
                    try:
                        weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                        weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                        if 375 <= weight <= 425 or 715 <= weight <= 765:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22;")
                        else:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
                    except Exception:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
            QApplication.processEvents()
            time.sleep(0.05)
        # After button press, check weights
        weights = []
        failed_stations = []
        for i in range(NUM_STATIONS):
            if station_enabled[i]:
                try:
                    weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                    weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                    weights.append((i, weight))
                    if 375 <= weight <= 425 or 725 <= weight <= 775:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22;")
                    else:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
                        failed_stations.append(str(i + 1))
                except Exception:
                    failed_stations.append(str(i + 1))
        in_first_range = [i for i, w in weights if 375 <= w <= 425]
        in_second_range = [i for i, w in weights if 715 <= w <= 765]
        if len(in_first_range) == len(weights):
            failed_stations = []
            target_weight_local = 400
        elif len(in_second_range) == len(weights):
            failed_stations = []
            target_weight_local = 750
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
                tr("ERROR") + " " +
                tr("ON STATION") +
                ("S" if len(failed_stations) > 1 else "") +
                " " + ", ".join(failed_stations) +
                "<br>" + tr("ALL STATIONS MUST USE THE SAME SIZE") + "<br>" + tr("PRESS SELECT TO CONTINUE")
            )
            calib_dialog.done(0)
            continue
        else:
            calib_dialog.accept()
            break

    # --- Step 5: Empty Bottle Check (Live update loop) ---
    calib_dialog = CalibrationDialog(station_enabled, parent=None)
    calib_dialog.set_main_label(tr("CALIBRATION_TITLE"))
    calib_dialog.set_sub_label(tr("Place an empty bottle in each active station"))
    calib_dialog.set_bottom_label(tr("PRESS SELECT TO CONTINUE"))
    calib_dialog.setModal(True)
    calib_dialog.resize(900, 500)
    calib_dialog.move(
        calib_dialog.screen().geometry().center() - calib_dialog.rect().center()
    )
    calib_dialog.show()
    QApplication.processEvents()
    while True:
        while calib_dialog.result() == 0:
            for i in range(NUM_STATIONS):
                if station_enabled[i]:
                    try:
                        weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                        weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                        if target_weight_local == 400:
                            in_range = 18 <= weight <= 22
                        elif target_weight_local == 750:
                            in_range = 29 <= weight <= 33
                        else:
                            in_range = False
                        if in_range:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22;")
                        else:
                            calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
                    except Exception:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
            QApplication.processEvents()
            time.sleep(0.05)
        failed_stations = []
        for i in range(NUM_STATIONS):
            if station_enabled[i]:
                try:
                    weight_text = calib_dialog.weight_labels[i].text().replace(" g", "")
                    weight = float(weight_text) if weight_text not in ("--", "") else 0.0
                    if target_weight_local == 400:
                        in_range = 18 <= weight <= 22
                    elif target_weight_local == 750:
                        in_range = 29 <= weight <= 33
                    else:
                        in_range = False
                    if in_range:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #228B22;")
                    else:
                        calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
                        failed_stations.append(str(i + 1))
                except Exception:
                    calib_dialog.weight_labels[i].setStyleSheet("color: #fff; background: #B22222;")
                    failed_stations.append(str(i + 1))
        if not failed_stations:
            calib_dialog.accept()
            break
        else:
            calib_dialog.set_bottom_label(
                tr("ERROR") + " " +
                tr("ON STATION") +
                ("S" if len(failed_stations) > 1 else "") +
                " " + ", ".join(failed_stations)
            )
            for _ in range(3):
                ping_buzzer()
                time.sleep(0.15)
            calib_dialog.set_bottom_label(tr("PRESS SELECT TO CONTINUE"))
            calib_dialog.done(0)
            continue

    # --- Final Setup: Button Check ---
    button_error_counts = [0] * NUM_STATIONS
    faulty_stations = set()
    timeout = 6
    start_time = time.time()
    calib_dialog.set_main_label(tr("BUTTON CHECK"))
    calib_dialog.set_sub_label(tr("Checking station buttons for faults..."))
    calib_dialog.set_bottom_label(tr("Checking... {timeout} seconds remaining").format(timeout=timeout))
    for i in range(NUM_STATIONS):
        if station_enabled[i]:
            calib_dialog.weight_labels[i].setText(tr("STATION") + f" {i+1}: " + tr("OK"))
            calib_dialog.weight_labels[i].setStyleSheet(
                "color: #fff; background: #228B22; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
            )
            calib_dialog.weight_labels[i].setFixedWidth(180)
        else:
            calib_dialog.weight_labels[i].setText(tr("STATION") + f" {i+1}: " + tr("DISABLED"))
            calib_dialog.weight_labels[i].setStyleSheet(
                "color: #fff; background: #888; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
            )
            calib_dialog.weight_labels[i].setFixedWidth(180)
    calib_dialog.resize(1200, 400)
    calib_dialog.show()
    QApplication.processEvents()
    last_seconds_left = timeout
    while True:
        elapsed = time.time() - start_time
        seconds_left = max(0, int(timeout - elapsed))
        if seconds_left != last_seconds_left:
            calib_dialog.set_bottom_label(tr("Checking... {timeout} seconds remaining").format(timeout=seconds_left))
            last_seconds_left = seconds_left
            QApplication.processEvents()
        for i in range(NUM_STATIONS):
            if station_enabled[i] and i not in faulty_stations and arduinos_local[i] and arduinos_local[i].in_waiting > 0:
                try:
                    byte = arduinos_local[i].read(1)
                    if byte == BUTTON_ERROR:
                        button_error_counts[i] += 1
                        if button_error_counts[i] >= 2 and i not in faulty_stations:
                            faulty_stations.add(i)
                            calib_dialog.weight_labels[i].setText(tr("STATION") + f" {i+1}: " + tr("BUTTON ERROR"))
                            calib_dialog.weight_labels[i].setStyleSheet(
                                "color: #fff; background: #B22222; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                            )
                            calib_dialog.weight_labels[i].setFixedWidth(180)
                            calib_dialog.set_sub_label(tr("STATION") + f" {i+1} " + tr("button is malfunctioning."))
                            calib_dialog.set_bottom_label(tr("For your safety, station {station} has been disabled<br>Checking... {timeout} seconds remaining").format(station=i+1, timeout=seconds_left))
                            station_enabled[i] = False
                            save_station_enabled(config_file, station_enabled)
                            QApplication.processEvents()
                    elif byte == CURRENT_WEIGHT:
                        extra = arduinos_local[i].read(4)
                except Exception:
                    pass
        for i in range(NUM_STATIONS):
            if station_enabled[i] and i not in faulty_stations:
                calib_dialog.weight_labels[i].setText(tr("STATION") + f" {i+1}: " + tr("OK"))
                calib_dialog.weight_labels[i].setStyleSheet(
                    "color: #fff; background: #228B22; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                )
                calib_dialog.weight_labels[i].setFixedWidth(180)
            elif not station_enabled[i]:
                calib_dialog.weight_labels[i].setText(tr("STATION") + f" {i+1}: " + tr("DISABLED"))
                calib_dialog.weight_labels[i].setStyleSheet(
                    "color: #fff; background: #888; border-radius: 8px; font-size: 20px; padding: 8px 16px; min-width: 180px;"
                )
                calib_dialog.weight_labels[i].setFixedWidth(180)
        QApplication.processEvents()
        time.sleep(0.05)
        if elapsed >= timeout:
            break
    if not faulty_stations:
        calib_dialog.set_sub_label(tr("Calibration complete."))
    else:
        calib_dialog.set_sub_label(tr("Some stations disabled due to button error."))
    calib_dialog.set_bottom_label(tr("PRESS SELECT TO CONTINUE"))
    QApplication.processEvents()
    while calib_dialog.result() == 0:
        QApplication.processEvents()
        time.sleep(0.01)
    calib_dialog.accept()

    # Return all state needed for the main window
    return {
        "station_enabled": station_enabled,
        "scale_calibrations": scale_calibrations_local,
        "target_weight": target_weight_local,
        "time_limit": time_limit,
        "filling_mode": filling_mode,
        "arduinos": arduinos_local,
    }

def main():
    try:
        logging.info("Starting main application.")
        app_qt = QApplication(sys.argv)

        # --- Run startup sequence (no main window yet) ---
        startup_state = run_startup_sequence(app_qt)

        # --- Now create and show the main window ---
        app = RelayControlApp(
            station_enabled=startup_state["station_enabled"],
            filling_mode_callback=filling_mode_callback
        )
        app.set_calibrate = None
        app.target_weight = startup_state.get("target_weight", 500.0)
        app.time_limit = startup_state.get("time_limit", 3000)
        app.filling_mode = startup_state.get("filling_mode", "AUTO")

        # If you want to pass the arduinos to the app, you can do so here
        global arduinos
        arduinos = startup_state.get("arduinos", [None] * NUM_STATIONS)

        for i, widget in enumerate(app.station_widgets):
            if startup_state["station_enabled"][i]:
                widget.set_weight(0, app.target_weight)

        GPIO.output(RELAY_POWER_PIN, GPIO.HIGH)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        timer = QTimer()
        timer.timeout.connect(lambda: poll_hardware(app))
        timer.start(35)

        button_timer = QTimer()
        button_timer.timeout.connect(lambda: handle_button_presses(app))
        button_timer.start(50)

        app.show()  # Only show after startup is complete

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