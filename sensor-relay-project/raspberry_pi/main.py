import os
import logging
import config
import sys
import time
import signal
import serial
import RPi.GPIO as GPIO # type: ignore
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer, Qt
from gui.gui import RelayControlApp, MenuDialog, SelectionDialog, InfoDialog, StartupWizardDialog
from gui.languages import LANGUAGES
import re
from config import STATS_LOG_FILE, STATS_LOG_DIR

# === ERROR LOGGING (MINIMAL) ===
ERROR_LOG_DIR = "logs/errors"
os.makedirs(ERROR_LOG_DIR, exist_ok=True)

ERROR_LOG_FILE = os.path.join(
    ERROR_LOG_DIR,
    f"error_log_{datetime.now().strftime('%Y-%m-%d')}.txt"
)

logging.basicConfig(
    filename=ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print(f"Logging to: {os.path.abspath(ERROR_LOG_FILE)}")

logging.error("Test error log entry: If you see this, logging is working.")

# ========== CONFIG & CONSTANTS ==========
NUM_STATIONS = 4
config_file = "config.txt"
target_weight = 500.0
time_limit = 3000
scale_calibrations = []
DEBUG = True

# ========== GLOBALS ==========
E_STOP = False
PREV_E_STOP_STATE = GPIO.HIGH
FILL_LOCKED = False
last_fill_time = [None] * NUM_STATIONS
last_final_weight = [None] * NUM_STATIONS
fill_time_limit_reached = False
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
arduinos = [None] * NUM_STATIONS
station_connected = [arduino is not None for arduino in arduinos]
serial_numbers = [arduino.serial_number if arduino else None for arduino in arduinos]
filling_mode = "AUTO"  # Default mode
station_max_weight_error = [False] * NUM_STATIONS
BOTTLE_WEIGHT_TOLERANCE = 25
RELAY_POWER_ENABLED = False  # Add this global flag

# ========== MESSAGE HANDLERS ==========
def handle_request_target_weight(station_index, arduino, **ctx):
    try:
        # Reject fill requests until relay power is enabled
        if not RELAY_POWER_ENABLED:
            if DEBUG:
                print(f"Station {station_index+1}: Fill request rejected, relay power not enabled yet. Sending STOP.")
            arduino.write(config.STOP)  # Send STOP to Arduino to abort fill
            return
        if ctx['FILL_LOCKED']:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Fill locked, sending STOP_FILL")
            arduino.write(config.STOP)
        else:
            arduino.write(config.TARGET_WEIGHT)
            arduino.write(f"{ctx['target_weight']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_target_weight", exc_info=True)

def handle_request_calibration(station_index, arduino, **ctx):
    try:
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {ctx['scale_calibrations'][station_index]}")
        arduino.write(config.REQUEST_CALIBRATION)
        arduino.write(f"{ctx['scale_calibrations'][station_index]}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_calibration", exc_info=True)

def handle_request_time_limit(station_index, arduino, **ctx):
    try:
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: REQUEST_TIME_LIMIT")
        arduino.write(config.REQUEST_TIME_LIMIT)
        arduino.write(f"{ctx['time_limit']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_time_limit", exc_info=True)

def handle_current_weight(station_index, arduino, **ctx):
    try:
        weight_bytes = arduino.read(4)
        print(f"[DEBUG][handle_current_weight] raw bytes: {weight_bytes!r}")
        if len(weight_bytes) == 4:
            weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            print(f"[DEBUG][handle_current_weight] parsed weight: {weight}")
            widgets = ctx.get('station_widgets')
            app = ctx.get('app')
            target_weight = ctx.get('target_weight', 500.0)
            unit = getattr(app, "units", "g") if app else "g"
            if widgets:
                widget = widgets[station_index]
                if station_max_weight_error[station_index]:
                    widget.weight_label.setStyleSheet("color: #FF2222;")
                else:
                    widget.weight_label.setStyleSheet("color: #fff;")
                if hasattr(widget, "set_weight"):
                    widget.set_weight(weight, target_weight, unit)
                else:
                    if widget.weight_label:
                        if unit == "g":
                            widget.weight_label.setText(f"{int(round(weight))} g")
                        else:
                            oz = weight / 28.3495
                            widget.weight_label.setText(f"{oz:.1f} oz")
            # StartupWizardDialog support
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "StartupWizardDialog":
                # print(f"[DEBUG] Calling set_weight on StartupWizardDialog for station {station_index} with weight {weight}")
                ctx['active_dialog'].set_weight(station_index, weight)
        else:
            logging.error(f"Station {station_index}: Incomplete weight bytes received: {weight_bytes!r}")
            widgets = ctx.get('station_widgets')
            if widgets:
                widget = widgets[station_index]
                if widget.weight_label:
                    widget.weight_label.setText("0.0 g")
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "StartupWizardDialog":
                ctx['active_dialog'].set_weight(station_index, 0.0)
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
    print(f"[DEBUG] handle_final_weight called for station {station_index}")
    try:
        weight_bytes = arduino.read(4)
        print(f"[DEBUG][handle_final_weight] raw bytes: {weight_bytes!r}")
        if len(weight_bytes) == 4:
            final_weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            print(f"[DEBUG][handle_final_weight] parsed final_weight: {final_weight}")
            last_final_weight[station_index] = final_weight

            print("About to call update_station_status in handle_final_weight")
            update_station_status(
                ctx.get('app'),
                station_index,
                final_weight,  # Always use this value
                ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                is_filling=False,
                fill_result="complete",
                fill_time=None  # No time yet
            )

            fill_time = last_fill_time[station_index]
            if fill_time is not None:
                seconds = int(round(fill_time / 1000))
                update_station_status(
                    ctx.get('app'),
                    station_index,
                    final_weight,
                    ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                    is_filling=False,
                    fill_result="complete",
                    fill_time=seconds
                )
                last_fill_time[station_index] = None
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
            final_weight = last_final_weight[station_index]
            if final_weight is not None:
                seconds = int(round(fill_time / 1000))
                # If fill_time reached the time limit, treat as timeout
                if fill_time >= ctx.get('time_limit', 3000):
                    update_station_status(
                        ctx.get('app'),
                        station_index,
                        final_weight,
                        ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                        is_filling=False,
                        fill_result="timeout",
                        fill_time=seconds
                    )
                else:
                    update_station_status(
                        ctx.get('app'),
                        station_index,
                        final_weight,
                        ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                        is_filling=False,
                        fill_result="complete",
                        fill_time=seconds
                    )
                last_fill_time[station_index] = None
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
    config.REQUEST_TARGET_WEIGHT: handle_request_target_weight,
    config.REQUEST_CALIBRATION: handle_request_calibration,
    config.REQUEST_TIME_LIMIT: handle_request_time_limit,
    config.CURRENT_WEIGHT: handle_current_weight,
    config.BEGIN_AUTO_FILL: handle_begin_auto_fill,
    config.BEGIN_SMART_FILL: handle_begin_smart_fill,
    config.FINAL_WEIGHT: handle_final_weight,
    config.FILL_TIME: handle_fill_time,
    config.MAX_WEIGHT_WARNING: handle_max_weight_warning,
    config.MAX_WEIGHT_END: handle_max_weight_end,  # <-- Register the new handler
}

# ========== UTILITY FUNCTIONS ==========
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

def load_bottle_sizes(config_path):
    bottle_sizes = {}
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("bottle_"):
                    key, value = line.split("=")
                    name = key.replace("bottle_", "")
                    parts = value.split(":")
                    if len(parts) == 3:
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        default_time_limit = int(parts[2])
                        bottle_sizes[name] = (full_weight, empty_weight, default_time_limit)
                    elif len(parts) == 2:
                        # fallback for old format
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        bottle_sizes[name] = (full_weight, empty_weight, None)
    except Exception as e:
        if DEBUG:
            print(f"Error loading bottle sizes: {e}")
    if DEBUG:
        print(f"[DEBUG] Loaded bottle sizes: {bottle_sizes}")
    return bottle_sizes

def load_bottle_weight_ranges(config_path, tolerance=BOTTLE_WEIGHT_TOLERANCE):
    bottle_ranges = {}
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("bottle_"):
                    key, value = line.split("=")
                    name = key.replace("bottle_", "")
                    parts = value.split(":")
                    if len(parts) >= 2:
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        bottle_ranges[name] = {
                            "full": (full_weight - tolerance, full_weight + tolerance),
                            "empty": (empty_weight - tolerance, empty_weight + tolerance)
                        }
                        # Optionally store time limit if present
                        if len(parts) == 3:
                            bottle_ranges[name]["default_time_limit"] = int(parts[2])
    except Exception as e:
        if DEBUG:
            print(f"Error loading bottle weight ranges: {e}")
    return bottle_ranges

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
        GPIO.setup(config.UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config.DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config.SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config.E_STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(config.BUZZER_PIN, GPIO.OUT)
        GPIO.output(config.BUZZER_PIN, GPIO.LOW)
        GPIO.setup(config.RELAY_POWER_PIN, GPIO.OUT)
        if DEBUG:
            print('GPIO setup complete')
    except Exception as e:
        logging.error(f"Error in setup_gpio: {e}")

def ping_buzzer(duration=0.05):
    GPIO.output(config.BUZZER_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(config.BUZZER_PIN, GPIO.LOW)

def ping_buzzer_invalid():
    GPIO.output(config.BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(config.BUZZER_PIN, GPIO.LOW)
    time.sleep(0.05)
    GPIO.output(config.BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(config.BUZZER_PIN, GPIO.LOW)

# ========== SESSION/DATA LOGGING ==========

def log_final_weight(station_index, final_weight):
    os.makedirs(STATS_LOG_DIR, exist_ok=True)
    with open(STATS_LOG_FILE, "a") as f:
        f.write(f"{datetime.now().isoformat()} session={SESSION_ID} station={station_index+1} weight={final_weight}\n")

# ========== STARTUP ==========

def startup(after_startup):
    global arduinos, scale_calibrations, station_enabled, station_serials, DEBUG

    # --- 1. Load calibration, serials, enabled states ---
    load_scale_calibrations()
    station_serials = load_station_serials()
    station_enabled = load_station_enabled(config_file)
    bottle_sizes = load_bottle_sizes(config_file)
    bottle_ranges = load_bottle_weight_ranges(config_file, tolerance=BOTTLE_WEIGHT_TOLERANCE)

    # --- 2. Connect and initialize Arduinos ---
    if DEBUG:
        print("[DEBUG] Connecting and initializing Arduinos...")
    station_connected = [False] * NUM_STATIONS
    arduinos = [None] * NUM_STATIONS
    for port in config.arduino_ports:
        try:
            if DEBUG:
                print(f"[DEBUG] Trying port {port}...")
            arduino = serial.Serial(port, 9600, timeout=0.5)
            arduino.reset_input_buffer()
            arduino.write(config.RESET_HANDSHAKE)
            arduino.flush()
            arduino.write(b'PMID')
            arduino.flush()
            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    if DEBUG:
                        print(f"[DEBUG] Received from {port}: {repr(line)}")
                    match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                    if match:
                        station_serial_number = match.group(1)
                        if DEBUG:
                            print(f"[DEBUG] Station serial {station_serial_number} detected on {port}")
                        break
                time.sleep(0.1)
            if station_serial_number is None or station_serial_number not in station_serials:
                if DEBUG:
                    print(f"[DEBUG] No recognized station detected on port {port}, skipping...")
                arduino.close()
                continue
            station_index = station_serials.index(station_serial_number)
            arduino.write(config.CONFIRM_ID)
            arduino.flush()
            if DEBUG:
                print(f"[DEBUG] Sent CONFIRM_ID to station {station_index+1} on {port}")
            got_request = False
            for _ in range(40):
                if arduino.in_waiting > 0:
                    req = arduino.read(1)
                    if req == config.REQUEST_CALIBRATION:
                        if DEBUG:
                            print(f"[DEBUG] Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                        arduino.write(config.REQUEST_CALIBRATION)
                        arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                        got_request = True
                        break
                    else:
                        arduino.reset_input_buffer()
                time.sleep(0.1)
            if not got_request:
                if DEBUG:
                    print(f"[DEBUG] Station {station_index+1}: Did not receive calibration request, skipping.")
                arduino.close()
                continue
            arduinos[station_index] = arduino
            station_connected[station_index] = True
            if DEBUG:
                print(f"[DEBUG] Station {station_index+1} on {port} initialized and ready.")
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] Error initializing Arduino on {port}: {e}")

    # --- 3. Wait for E-STOP release ---
    if DEBUG:
        print("[DEBUG] Checking E-STOP state...")
    while GPIO.input(config.E_STOP_PIN) == GPIO.LOW:
        time.sleep(0.1)
    if DEBUG:
        print("[DEBUG] E-STOP released, continuing startup.")

    # --- 3.5. Create StartupWizardDialog ---
    app = QApplication.instance() or QApplication(sys.argv)

    wizard = StartupWizardDialog(num_stations=NUM_STATIONS, bottle_ranges=bottle_ranges)
    app.active_dialog = wizard
    
    # Set correct labels for station verification
    wizard.set_station_labels(
        names=[f"Station {i+1}" for i in range(NUM_STATIONS)],
        connected=station_connected,
        enabled=station_enabled
    )
    
    wizard.show_station_verification()
    wizard.show()

    step_result = {}

    def on_step_completed(info):
        step_result.clear()
        step_result.update(info)

    wizard.step_completed.connect(on_step_completed)

    # --- 4. Station verification dialog ---
    wizard.show_station_verification()
    wizard.show()

    # Wait for user to finish station verification
    while not step_result or step_result.get("step") != "station_verification":
        app.processEvents()
        time.sleep(0.01)

    # Now open the filling mode selection dialog
    options = [
        ("AUTO", "Auto Mode"),
        ("MANUAL", "Manual Mode"),
        ("SMART", "Smart Mode")
    ]
    selection_dialog = SelectionDialog(options=options, title="FILLING MODE")
    selection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    selection_dialog.show()
    app.active_dialog = selection_dialog

    filling_mode_selected = None
    def on_select(mode, index):
        nonlocal filling_mode_selected
        filling_mode_selected = mode
        filling_mode_callback(mode)
        selection_dialog.accept()
    selection_dialog.on_select_callback = on_select

    while selection_dialog.isVisible():
        app.processEvents()
        time.sleep(0.01)

    app.active_dialog = wizard

    # --- 6. Calibration Step: Clear all scales ---
    step_result.clear()
    while True:
        wizard.show_empty_scale_prompt()
        wizard.show()
        while not step_result or step_result.get("step") != "empty_scale":
            app.processEvents()
            time.sleep(0.01)

        # Check if any scale > 20g
        scale_values = [wizard.get_weight(i) for i in range(NUM_STATIONS) if station_enabled[i] and station_connected[i]]
        if any(w > 20 for w in scale_values):
            options = [("CONFIRM", "CONFIRM"), ("BACK", "BACK")]
            selection_dialog = SelectionDialog(options=options, title="Confirm All Scales Are Clear")
            selection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            selection_dialog.show()
            app.active_dialog = selection_dialog
            user_choice = None
            def on_select(opt, idx):
                nonlocal user_choice
                user_choice = opt
                selection_dialog.accept()
            selection_dialog.on_select_callback = on_select
            while selection_dialog.isVisible():
                app.processEvents()
                time.sleep(0.01)
            app.active_dialog = wizard
            if user_choice == "CONFIRM":
                break  # Proceed to next step
            else:
                step_result.clear()  # Retry clear scale step
                continue
        else:
            break  # All scales are clear, proceed

    # Send TARE_SCALE to each enabled and connected Arduino
    for i, arduino in enumerate(arduinos):
        if arduino and station_enabled[i] and station_connected[i]:
            try:
                arduino.write(config.TARE_SCALE)
                arduino.flush()
            except Exception as e:
                logging.error(f"Error sending TARE_SCALE to station {i+1}: {e}")

    # SKIP WAITING FOR TARE CONFIRMATION, just move on to next step

    # --- 7. Calibration Step: Place full bottles ---
    # Build all full bottle ranges from config
    full_ranges = {
        name: bottle_ranges[name]["full"]
        for name in bottle_ranges
    }
    wizard.show_full_bottle_prompt(full_ranges)
    wizard.show()
    step_result.clear()


    selected_bottle_id = None
    while True:
        # Wait for user to press CONTINUE
        while not step_result or step_result.get("step") != "full_bottle":
            app.processEvents()
            time.sleep(0.01)

        # After CONTINUE is pressed, check all active stations
        active_weights = [
            wizard.get_weight(i)
            for i in range(NUM_STATIONS)
            if station_enabled[i] and station_connected[i]
        ]

        # Find which bottle range all weights fit into
        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        found = False
        for bottle_id, rng in full_ranges.items():
            if all(in_range(w, rng) for w in active_weights):
                selected_bottle_id = bottle_id
                found = True
                break

        if not found:
            dlg = InfoDialog("Error", "All bottles must be within the same size range.", wizard)
            ping_buzzer_invalid()
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.show()
            QTimer.singleShot(2000, dlg.accept)
            step_result.clear()  # Wait for user to try again
            continue
        else:
            break  # Proceed to next step

    # Set target_weight and time_limit based on selected bottle
    if selected_bottle_id:
        bottle_config_line = None
        with open(config_file, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"bottle_{selected_bottle_id}"):
                    bottle_config_line = line
                    break
        if bottle_config_line:
            parts = bottle_config_line.split("=")[1].split(":")
            if len(parts) >= 3:
                try:
                    target_weight = float(parts[0])
                    time_limit = int(parts[2])
                    if DEBUG:
                        print(f"[DEBUG] Set target_weight to {target_weight} and time_limit to {time_limit} for bottle {selected_bottle_id}")
                except Exception as e:
                    print(f"[DEBUG] Error parsing bottle config for {selected_bottle_id}: {e}")

    # Now show empty bottle prompt
    wizard.show_empty_bottle_prompt()
    wizard.show()


    # --- 8. Calibration Step: Place empty bottles ---
    # Use the selected bottle's empty range from config
    if selected_bottle_id and selected_bottle_id in bottle_ranges:
        empty_range = bottle_ranges[selected_bottle_id]["empty"]
    else:
        empty_range = (0, 0)

    wizard.show_empty_bottle_prompt(empty_range=empty_range)
    wizard.show()

    while True:
        step_result.clear()
        while not step_result or step_result.get("step") != "empty_bottle":
            app.processEvents()
            time.sleep(0.01)

        # After CONTINUE is pressed, check all active stations
        active_weights = [
            wizard.get_weight(i)
            for i in range(NUM_STATIONS)
            if station_enabled[i] and station_connected[i]
        ]

        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        # Only check that all weights are within the selected bottle's empty range
        if not all(in_range(w, bottle_ranges[selected_bottle_id]["empty"]) for w in active_weights):
            dlg = InfoDialog("Error", "All bottles must be within the empty bottle weight range.", wizard)
            ping_buzzer_invalid()
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.show()
            QTimer.singleShot(2000, dlg.accept)
            continue
        else:
            # Set target_weight and time_limit using the selected bottle ID from full bottle step
            bottle_config_line = None
            with open(config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(f"bottle_{selected_bottle_id}"):
                        bottle_config_line = line
                        break
            if bottle_config_line:
                parts = bottle_config_line.split("=")[1].split(":")
                try:
                    globals()['target_weight'] = float(parts[0])
                    if len(parts) >= 3:
                        globals()['time_limit'] = int(parts[2])
                    else:
                        globals()['time_limit'] = 3000
                    if DEBUG:
                        print(f"[DEBUG] (empty bottle step) Set target_weight to {globals()['target_weight']} and time_limit to {globals()['time_limit']} for bottle {selected_bottle_id}")
                except Exception as e:
                    print(f"[DEBUG] Error parsing bottle config for {selected_bottle_id}: {e}")
            after_startup()
            wizard.finish_wizard()
            app.active_dialog = app
            break


def filling_mode_callback(mode):
    global filling_mode
    filling_mode = mode
    if DEBUG:
        print(f"[main.py] Filling mode set to: {mode}")

    if mode == "MANUAL":
        for i, arduino in enumerate(arduinos):
            if arduino and station_enabled[i]:
                try:
                    arduino.write(bytes([0x20]))  # MANUAL_FILL_START
                    arduino.flush()
                    if DEBUG:
                        print(f"[main.py] Sent MANUAL_FILL_START to station {i+1}")
                except Exception as e:
                    print(f"[main.py] Failed to send MANUAL_FILL_START to station {i+1}: {e}")
    else:
        for i, arduino in enumerate(arduinos):
            if arduino and station_enabled[i]:
                try:
                    arduino.write(bytes([0x22]))  # EXIT_MANUAL_END
                    arduino.flush()
                    if DEBUG:
                        print(f"[main.py] Sent EXIT_MANUAL_END to station {i+1}")
                except Exception as e:
                    print(f"[main.py] Failed to send EXIT_MANUAL_END to station {i+1}: {e}")

def reconnect_arduino(station_index, port):
    if DEBUG:
        print(f"reconnect_arduino called for {port}")
    else:
        logging.info(f"reconnect_arduino called for {port}")
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

        arduino.write(config.RESET_HANDSHAKE)
        arduino.flush()
        if DEBUG:
            print(f"Sent RESET_HANDSHAKE to {port}")
        else:
            logging.info(f"Sent RESET_HANDSHAKE to {port}")
        time.sleep(0.5)

        arduino.write(b'PMID')
        arduino.flush()
        if DEBUG:
            print(f"Sent 'PMID' handshake to {port}")
        else:
            logging.info(f"Sent 'PMID' handshake to {port}")

        station_serials = load_station_serials()
        station_serial_number = None
        for _ in range(60):
            if arduino.in_waiting > 0:
                line = arduino.read_until(b'\n').decode(errors='replace').strip()
                if DEBUG:
                    print(f"Received from {port}: {repr(line)}")
                else:
                    logging.info(f"Received from {port}: {repr(line)}")
                match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                if match:
                    station_serial_number = match.group(1)
                    if DEBUG:
                        print(f"Station serial {station_serial_number} detected on {port}")
                    else:
                        logging.info(f"Station serial {station_serial_number} detected on {port}")
                    break
            time.sleep(0.1)
        if station_serial_number is None or station_serial_number not in station_serials:
            if DEBUG:
                print(f"No recognized station detected on port {port}, skipping...")
            else:
                logging.error(f"No recognized station detected on port {port}, skipping...")
            arduino.close()
            return False

        station_index = station_serials.index(station_serial_number)

        arduino.write(config.CONFIRM_ID)
        arduino.flush()
        if DEBUG:
            print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")
        else:
            logging.info(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

        got_request = False
        for _ in range(40):
            if arduino.in_waiting > 0:
                req = arduino.read(1)
                if req == config.REQUEST_CALIBRATION:
                    if DEBUG:
                        print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                    else:
                        logging.info(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                    arduino.write(config.REQUEST_CALIBRATION)
                    arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                    got_request = True
                    break
                else:
                    arduino.reset_input_buffer()
            time.sleep(0.1)
        if not got_request:
            if DEBUG:
                print(f"Station {station_index+1}: Did not receive calibration request, skipping.")
            else:
                logging.error(f"Station {station_index+1}: Did not receive calibration request, skipping.")
            arduino.close()
            return False

        arduinos[station_index - 1] = arduino
        if DEBUG:
            print(f"Station {station_index+1} on {port} reconnected and ready.")
        else:
            logging.info(f"Station {station_index+1} on {port} reconnected and ready.")
        return True

    except Exception as e:
        if DEBUG:
            print(f"Error reconnecting Arduino on {port}: {e}")
        logging.error(f"Error reconnecting Arduino on {port}: {e}")
        return False

def try_connect_station(station_index):
    port = config.arduino_ports[station_index]
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
        active_dialog = getattr(app, "active_dialog", None)
        filling_mode = getattr(app, "filling_mode", "AUTO")
        overlay_widget = getattr(app, "overlay_widget", None)
        refresh_ui = getattr(app, "refresh_ui", None)

        # --- Unified station_widgets selection ---
        if active_dialog and hasattr(active_dialog, "station_widgets"):
            station_widgets = active_dialog.station_widgets
        else:
            station_widgets = getattr(app, "station_widgets", None)

        estop_pressed = GPIO.input(config.E_STOP_PIN) == GPIO.LOW

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
                    arduino.write(config.E_STOP_ACTIVATED)
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

                # if DEBUG:
                    # print(f"[poll_hardware] Station {station_index+1}: in_waiting={arduino.in_waiting}")

                while arduino.in_waiting > 0:
                    message_type = arduino.read(1)
                    # if DEBUG:
                    #     print(f"[poll_hardware] Station {station_index+1}: message_type={message_type!r}")
                    handler = MESSAGE_HANDLERS.get(message_type)
                    # --- Unified context for handlers ---
                    ctx = {
                        'FILL_LOCKED': FILL_LOCKED,
                        'DEBUG': DEBUG,
                        'target_weight': getattr(app, "target_weight", target_weight),
                        'scale_calibrations': scale_calibrations,
                        'time_limit': getattr(app, "time_limit", time_limit),
                        'active_dialog': active_dialog,
                        'station_widgets': station_widgets,
                        'refresh_ui': refresh_ui,
                        'app': app,
                    }
                    # Remove legacy update_station_weight logic
                    # Weight updates should use widget.set_weight directly

                    if handler:
                        handler(station_index, arduino, **ctx)
                    else:
                        handle_unknown(station_index, arduino, message_type, **ctx)
            except serial.SerialException as e:
                if DEBUG:
                    print(f"Lost connection to Arduino {station_index+1}: {e}")
                port = config.arduino_ports[station_index]
                reconnect_arduino(station_index, port)
            except Exception as e:
                if DEBUG:
                    print(f"[poll_hardware] Exception for station {station_index+1}: {e}")
                logging.error(f"Error in poll_hardware: {e}")
    except Exception as e:
        logging.error(f"Error in poll_hardware: {e}")
        if DEBUG:
            print(f"Error in poll_hardware: {e}")

# ========== GUI/BUTTON HANDLING ==========

def handle_button_presses(app):
    global DEBUG
    try:
        dialog = getattr(app, "active_dialog", None)

        # If dialog is None, this is an error state
        if dialog is None:
            error_msg = "ERROR: No active dialog! Button press ignored."
            print(error_msg)
            logging.error(error_msg)
            return

        # Helper: flash icon if button_column exists
        def flash_dialog_icon(index):
            if dialog is not None and hasattr(dialog, "button_column"):
                dialog.button_column.flash_icon(index)
            elif hasattr(app, "button_column"):
                app.button_column.flash_icon(index)

        # UP BUTTON
        if GPIO.input(config.UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"UP button pressed, dialog: {dialog}")
            flash_dialog_icon(0)
            if hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("up")
            while GPIO.input(config.UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            dialog.select_prev()
            if hasattr(dialog, "set_arrow_inactive"):
                dialog.set_arrow_inactive("up")
            return

        # DOWN BUTTON
        if GPIO.input(config.DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"DOWN button pressed, dialog: {dialog}")
            flash_dialog_icon(2)
            if hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("down")
            while GPIO.input(config.DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            dialog.select_next()
            if hasattr(dialog, "set_arrow_inactive"):
                dialog.set_arrow_inactive("down")
            return

        # SELECT BUTTON
        if GPIO.input(config.SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"SELECT button pressed, dialog: {dialog}")
            flash_dialog_icon(1)
            while GPIO.input(config.SELECT_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            try:
                dialog.activate_selected()
            except Exception as e:
                logging.error("Error in dialog.activate_selected()", exc_info=True)
                if DEBUG:
                    print(f"Error in dialog.activate_selected(): {e}")
            return

    except Exception as e:
        logging.error("Error in handle_button_presses", exc_info=True)
        if DEBUG:
            print(f"Error in handle_button_presses: {e}")

def update_station_status(app, station_index, weight, filling_mode, is_filling, fill_result=None, fill_time=None):
    """
    Update the status label for a station.
    'weight' should be the final fill weight if called from handle_final_weight.
    """
    print(f"[DEBUG] update_station_status: idx={station_index}, weight={weight}, mode={filling_mode}, is_filling={is_filling}, fill_result={fill_result}, fill_time={fill_time}")
    widget = app.station_widgets[station_index]
    print(f"widget for station {station_index} is {widget}")
    if filling_mode == "AUTO":
        if fill_result == "complete":
            if fill_time is not None:
                widget.set_status(f"FINAL WEIGHT: {weight} g\nTIME: {fill_time:.2f}s", color="#11BD33")
            else:
                widget.set_status(f"FINAL WEIGHT: {weight} g", color="#11BD33")
        elif fill_result == "timeout":
            if fill_time is not None:
                widget.set_status(f"AUTO FILL TIMEOUT {fill_time:.2f}s", color="#F6EB61")
            else:
                widget.set_status("AUTO FILL TIMEOUT", color="#F6EB61")
        elif fill_result is None and is_filling:
            widget.set_status("AUTO FILL RUNNING", color="#F6EB61")
        elif weight < 40:
            widget.set_status("AUTO FILL READY", color="#11BD33")
        else:
            widget.set_status("READY", color="#fff")
    else:
        widget.set_status("READY", color="#fff")


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

        signal.signal(signal.SIGINT, signal.SIG_DFL)

        timer = QTimer()
        button_timer = QTimer()

        # Start button polling timer BEFORE startup
        button_timer.timeout.connect(lambda: handle_button_presses(app_qt))
        button_timer.start(50)

        # Start poll_hardware BEFORE startup
        timer.timeout.connect(lambda: poll_hardware(app_qt))
        timer.start(35)

        def after_startup():
            global RELAY_POWER_ENABLED
            app = RelayControlApp(
                station_enabled=station_enabled,
                filling_mode_callback=filling_mode_callback
            )
            app.set_calibrate = None
            app.target_weight = target_weight
            app.time_limit = time_limit
            app.filling_mode = filling_mode  # Ensure filling_mode is set

            for i, widget in enumerate(app.station_widgets):
                if station_enabled[i]:
                    widget.set_weight(0, target_weight, "g")

            timer.timeout.disconnect()
            timer.timeout.connect(lambda: poll_hardware(app))
            button_timer.timeout.disconnect()
            button_timer.timeout.connect(lambda: handle_button_presses(app))
            app.show()
            GPIO.output(config.RELAY_POWER_PIN, GPIO.HIGH)
            RELAY_POWER_ENABLED = True  # Set flag after relay power is enabled

            app.active_dialog = app

        # Run startup and pass after_startup as a callback
        startup(after_startup)

        app_qt.exec()
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