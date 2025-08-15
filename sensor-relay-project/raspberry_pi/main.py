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

os.makedirs(config.ERROR_LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=config.ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

print(f"Logging to: {config.ERROR_LOG_FILE}")

# Test log entry
logging.error("Test error log entry: If you see this, logging is working.")

# ========== CONFIG & CONSTANTS ==========
LOG_DIR = "logs/errors"
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(config.ERROR_LOG_DIR, exist_ok=True)
logging.basicConfig(
    filename=config.ERROR_LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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
        if len(weight_bytes) == 4:
            weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
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
        print(f"[DEBUG] weight_bytes: {weight_bytes!r}")
        if len(weight_bytes) == 4:
            final_weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            print(f"[DEBUG] final_weight: {final_weight}")
            last_final_weight[station_index] = final_weight

            print("About to call update_station_status in handle_final_weight")
            update_station_status(
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
                        station_index,
                        final_weight,
                        ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                        is_filling=False,
                        fill_result="timeout",
                        fill_time=seconds
                    )
                else:
                    update_station_status(
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

def startup(app, timer):
    global arduinos, scale_calibrations, station_enabled, station_serials

    print("[DEBUG] === Startup sequence initiated ===")

    # Load calibration and serials
    load_scale_calibrations()
    station_serials = load_station_serials()
    station_enabled = load_station_enabled(config_file)
    station_names = [app.tr("STATION") + f" {i+1}" for i in range(NUM_STATIONS)]

    # Connect and setup Arduinos
    station_connected = [False] * NUM_STATIONS
    arduinos = [None] * NUM_STATIONS
    for port in config.arduino_ports:
        try:
            if DEBUG:
                print(f"[DEBUG] Trying port {port}...")
            else:
                logging.info(f"Trying port {port}...")
            arduino = serial.Serial(port, 9600, timeout=0.5)
            arduino.reset_input_buffer()
            arduino.write(config.RESET_HANDSHAKE)
            arduino.flush()
            if DEBUG:
                print(f"[DEBUG] Sent RESET HANDSHAKE to {port}")
            else:
                logging.info(f"Sent RESET HANDSHAKE to {port}")
            arduino.write(b'PMID')
            arduino.flush()
            if DEBUG:
                print(f"[DEBUG] Sent 'PMID' handshake to {port}")
            else:
                logging.info(f"Sent 'PMID' handshake to {port}")
            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    if DEBUG:
                        print(f"[DEBUG] Received from {port}: {repr(line)}")
                    else:
                        logging.info(f"Received from {port}: {repr(line)}")
                    match = re.match(r"<SERIAL:(PM-SN\d{4})>", line)
                    if match:
                        station_serial_number = match.group(1)
                        if DEBUG:
                            print(f"[DEBUG] Station serial {station_serial_number} detected on {port}")
                        else:
                            logging.info(f"Station serial {station_serial_number} detected on {port}")
                        break
                time.sleep(0.1)
            if station_serial_number is None or station_serial_number not in station_serials:
                if DEBUG:
                    print(f"[DEBUG] No recognized station detected on port {port}, skipping...")
                else:
                    logging.error(f"No recognized station detected on port {port}, skipping...")
                arduino.close()
                continue
            station_index = station_serials.index(station_serial_number)
            arduino.write(config.CONFIRM_ID)
            arduino.flush()
            if DEBUG:
                print(f"[DEBUG] Sent CONFIRM_ID to station {station_index+1} on {port}")
            else:
                logging.info(f"Sent CONFIRM_ID to station {station_index+1} on {port}")
            got_request = False
            for _ in range(40):
                if arduino.in_waiting > 0:
                    req = arduino.read(1)
                    if req == config.REQUEST_CALIBRATION:
                        if DEBUG:
                            print(f"[DEBUG] Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
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
                    print(f"[DEBUG] Station {station_index+1}: Did not receive calibration request, skipping.")
                else:
                    logging.error(f"Station {station_index+1}: Did not receive calibration request, skipping.")
                arduino.close()
                continue
            arduinos[station_index] = arduino
            station_connected[station_index] = True
            if DEBUG:
                print(f"[DEBUG] Station {station_index+1} on {port} initialized and ready.")
            else:
                logging.info(f"Station {station_index+1} on {port} initialized and ready.")
        except Exception as e:
            if DEBUG:
                print(f"[DEBUG] Error initializing Arduino on {port}: {e}")
            logging.error(f"Error initializing Arduino on {port}: {e}")

    # Load enabled states
    try:
        if DEBUG:
            print("[DEBUG] Loading enabled states...")
        else:
            logging.info("Loading enabled states...")
        station_enabled = load_station_enabled("config.txt")
        if DEBUG:
            print(f"[DEBUG] station_enabled: {station_enabled}")
        else:
            logging.info(f"station_enabled: {station_enabled}")
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Error loading enabled states: {e}")
        logging.error(f"Error loading enabled states: {e}")

    # Wait for E-STOP to be released
    print("[DEBUG] Checking E-STOP state...")
    while GPIO.input(config.E_STOP_PIN) == GPIO.LOW:
        time.sleep(0.1)

    # --- Startup Wizard Dialog ---
    def on_station_verified():
        print("[DEBUG] Station verification accepted, triggering filling mode dialog")
        filling_modes = [("AUTO", app.tr("AUTO")), ("MANUAL", app.tr("MANUAL")), ("SMART", app.tr("SMART"))]

        def filling_mode_selected(mode, index):
            print(f"[DEBUG] filling_mode_selected called with mode={mode}, index={index}")
            app.filling_mode = mode
            global filling_mode
            filling_mode = mode

            if index == 1:  # MANUAL
                print("[DEBUG] MANUAL mode selected, showing InfoDialog and closing wizard.")
                MANUAL_FILL_START = b'\x20'
                for i, arduino in enumerate(arduinos):
                    if arduino and station_enabled[i]:
                        try:
                            arduino.write(MANUAL_FILL_START)
                            arduino.flush()
                        except Exception as e:
                            logging.error(f"Failed to send MANUAL_FILL_START to station {i+1}: {e}")
                info = InfoDialog(app.tr("MANUAL FILLING MODE"), app.tr("Manual filling mode selected.<br>Startup complete."), app)
                info.setWindowModality(Qt.WindowModality.ApplicationModal)
                info.show()
                QTimer.singleShot(2000, info.accept)
                QApplication.processEvents()
                print("[DEBUG] Accepting wizard (should close wizard)")
                wizard.accept()
                return

            elif index == 0:  # AUTO
                print("[DEBUG] AUTO mode selected, continuing startup wizard.")

            elif index == 2:  # SMART
                print("[DEBUG] SMART mode selected, continuing startup wizard.")

            print(f"[DEBUG] After filling_mode_selected: wizard.isVisible={wizard.isVisible()}")

        filling_mode_dialog = SelectionDialog(
            options=filling_modes,
            parent=wizard,  # Show on top of wizard
            title=app.tr("SET FILLING MODE"),
            on_select=filling_mode_selected
        )
        app.active_dialog = filling_mode_dialog
        print("[DEBUG] Showing SelectionDialog")
        filling_mode_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        filling_mode_dialog.show()
        while filling_mode_dialog.isVisible():
            QApplication.processEvents()
            time.sleep(0.01)
        print(f"[DEBUG] SelectionDialog closed. wizard.isVisible={wizard.isVisible()}")

    wizard = StartupWizardDialog(parent=app, num_stations=NUM_STATIONS, on_station_verified=on_station_verified)
    app.active_dialog = wizard
    wizard.setWindowState(Qt.WindowState.WindowFullScreen)

    print("[DEBUG] Showing StartupWizardDialog (exec)")
    wizard.set_step(0)
    wizard.set_main_label(f"CALIBRATION STEP {wizard.current_step + 1}")
    wizard.set_info_text(
        "Are these the filling stations you are using?\n"
        "Verify which stations are enabled and connected\n"
        "Press CONTINUE when ready"
    )
    wizard.set_station_labels(
        names=station_names,
        connected=station_connected,
        enabled=station_enabled
    )

    wizard.exec()
    print(f"[DEBUG] StartupWizardDialog closed? isVisible={wizard.isVisible()}")

    # Save enabled states after verification
    station_enabled = wizard.get_station_enabled()
    save_station_enabled(config_file, station_enabled)
    app.active_dialog = wizard

    # If MANUAL mode was selected, wizard is already closed, so exit startup
    if not wizard.isVisible():
        print("[DEBUG] Wizard closed after MANUAL mode, exiting startup.")
        return

    # --- Step 2: Calibration - Remove Weight ---
    wizard.set_step(2)
    print("[DEBUG] Set wizard to step 2 (Calibration - Remove Weight)")
    wizard.set_main_label(f"CALIBRATION STEP {wizard.current_step + 1}")
    wizard.set_info_text(
        "Remove all weight from each active station.\nPress CONTINUE when ready."
    )
    wizard.set_station_labels(
        names=station_names,
        connected=station_connected,
        enabled=station_enabled
    )
    # Wait for user to continue (handled inside dialog)

    # Tare all enabled stations after user confirms remove weight
    for i, arduino in enumerate(arduinos):
        if arduino and station_enabled[i]:
            try:
                arduino.write(config.TARE_SCALE)
                arduino.flush()
                print(f"[DEBUG] Sent TARE_SCALE to station {i+1}")
            except Exception as e:
                logging.error(f"Failed to send TARE_SCALE to station {i+1}: {e}")

    # --- Step 3: Full Bottle Check ---
    wizard.set_step(3)
    wizard.set_main_label(f"CALIBRATION STEP {wizard.current_step + 1}")
    wizard.set_info_text(
        "Place a full bottle in each active station.\nPress CONTINUE when ready."
    )
    wizard.set_station_labels(
        names=station_names,
        connected=station_connected,
        enabled=station_enabled
    )

    # --- Step 4: Empty Bottle Check ---
    wizard.set_step(4)
    wizard.set_main_label(f"CALIBRATION STEP {wizard.current_step + 1}")
    wizard.set_info_text(
        "Place an empty bottle in each active station.\nPress CONTINUE when ready."
    )
    wizard.set_station_labels(
        names=station_names,
        connected=station_connected,
        enabled=station_enabled
    )

    # --- Step 5: Button Check ---
    wizard.set_step(5)
    wizard.set_main_label(f"CALIBRATION STEP {wizard.current_step + 1}")
    wizard.set_info_text(
        "Checking station buttons for faults...\nPress CONTINUE when ready."
    )
    wizard.set_station_labels(
        names=station_names,
        connected=station_connected,
        enabled=station_enabled
    )

    wizard.accept()  # Close the wizard dialog after all steps
    app.active_dialog = None

    # Show the main window after startup is complete
    app.show()

    # If MANUAL mode, send MANUAL_FILL_START to all connected stations (unchanged)
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

                if DEBUG:
                    print(f"[poll_hardware] Station {station_index+1}: in_waiting={arduino.in_waiting}")

                while arduino.in_waiting > 0:
                    message_type = arduino.read(1)
                    if DEBUG:
                        print(f"[poll_hardware] Station {station_index+1}: message_type={message_type!r}")
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

        # Helper: flash icon if button_column exists
        def flash_dialog_icon(index):
            # Try to flash on the active dialog first
            if dialog is not None and hasattr(dialog, "button_column"):
                dialog.button_column.flash_icon(index)
            # If not, flash on the main app window
            elif hasattr(app, "button_column"):
                app.button_column.flash_icon(index)

        # UP BUTTON
        if GPIO.input(config.UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"UP button pressed, dialog: {dialog}")
            flash_dialog_icon(0)  # Flash UP icon
            if dialog is not None and hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("up")
            while GPIO.input(config.UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_prev()
                if hasattr(dialog, "set_arrow_inactive"):
                    dialog.set_arrow_inactive("up")
            return

        # DOWN BUTTON
        if GPIO.input(config.DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"DOWN button pressed, dialog: {dialog}")
            flash_dialog_icon(2)  # Flash DOWN icon
            if dialog is not None and hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("down")
            while GPIO.input(config.DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_next()
                if hasattr(dialog, "set_arrow_inactive"):
                    dialog.set_arrow_inactive("down")
            return

        # SELECT BUTTON
        if GPIO.input(config.SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"SELECT button pressed, dialog: {dialog}")
            flash_dialog_icon(1)  # Flash SELECT icon
            while GPIO.input(config.SELECT_BUTTON_PIN) == GPIO.LOW:
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
                widget.set_status(f"AUTO FILL COMPLETE {fill_time:.2f}s", color="#11BD33")
            else:
                widget.set_status("AUTO FILL COMPLETE", color="#11BD33")
        elif fill_result == "timeout":
            if fill_time is not None:
                widget.set_status(f"AUTO FILL TIMEOUT {fill_time:.2f}s", color="#F6EB61")
            else:
                widget.set_status("AUTO FILL TIMEOUT", color="#F6EB61")
        elif is_filling:
            widget.set_status("AUTO FILLING...", color="#F6EB61")
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
        app = RelayControlApp(
            station_enabled=station_enabled,
            filling_mode_callback=filling_mode_callback
        )
        app.set_calibrate = None  # Set if you have a calibrate_scale function

        app.target_weight = target_weight

        app.hide()  # <-- Add this line to hide the window during startup

        if DEBUG:
            print('app initialized, contacting arduinos')

        for i, widget in enumerate(app.station_widgets):
            if station_enabled[i]:
                widget.set_weight(0, target_weight, "g")

        GPIO.output(config.RELAY_POWER_PIN, GPIO.HIGH)
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