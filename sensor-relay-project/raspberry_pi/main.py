import os
import logging
import sys
import time
import signal
import serial
import config
from config import GPIO
from datetime import datetime
from PyQt6.QtWidgets import QApplication
import faulthandler
faulthandler.enable()
from PyQt6.QtCore import QTimer, Qt
from gui.gui import RelayControlApp, MenuDialog, SelectionDialog, InfoDialog, StartupWizardDialog
from gui.languages import LANGUAGES
import re
from message_handlers import MESSAGE_HANDLERS, handle_unknown
from message_handlers import MESSAGE_HANDLERS
from startup import (
    run_startup_sequence,
    step_load_serials_and_ranges,
    step_connect_arduinos,
    step_station_verification,
    step_clear_all_scales,
    step_filling_mode_selection,
    step_full_bottle_check,
    step_empty_bottle_check,
)

from utils import (
    load_scale_calibrations,
    load_station_enabled,
    save_station_enabled,
    load_station_serials,
    load_bottle_sizes,
    load_bottle_weight_ranges,
    clear_serial_buffer,
    update_station_status
)

from config import (
    NUM_STATIONS,
    config_file,
    target_weight,
    time_limit,
    scale_calibrations,
    DEBUG,
    E_STOP,
    FILL_LOCKED,
    last_fill_time,
    last_final_weight,
    fill_time_limit_reached,
    SESSION_ID,
    arduinos,
    station_connected,
    serial_numbers,
    filling_mode,
    station_max_weight_error,
    BOTTLE_WEIGHT_TOLERANCE,
    RELAY_POWER_ENABLED,
    UP_BUTTON_PIN,
    DOWN_BUTTON_PIN,
    SELECT_BUTTON_PIN,
    E_STOP_PIN,
    BUZZER_PIN,
    RELAY_POWER_PIN,
    CONFIRM_ID,
    RESET_HANDSHAKE,
    REQUEST_CALIBRATION,
    REQUEST_TARGET_WEIGHT,
    REQUEST_TIME_LIMIT,
    arduino_ports,
    E_STOP_ACTIVATED,
)

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
"""
def startup(after_startup):
    global arduinos, scale_calibrations, station_enabled, station_serials, DEBUG

    print("[DEBUG] startup: loading serials, bottle sizes, and ranges")
    station_serials = load_station_serials()
    bottle_sizes = load_bottle_sizes(config_file)
    bottle_ranges = load_bottle_weight_ranges(config_file, tolerance=BOTTLE_WEIGHT_TOLERANCE)

    print("[DEBUG] startup: connecting and initializing Arduinos...")
    station_connected = [False] * NUM_STATIONS
    arduinos = [None] * NUM_STATIONS
    for port in config.arduino_ports:
        try:
            if DEBUG:
                print(f"[DEBUG] Trying port {port}...")
            arduino = serial.Serial(port, 9600, timeout=0.5)
            if DEBUG:
                print(f"[DEBUG] Flushed serial buffer for {port}")
            # Send handshake sequence one byte at a time
            for b in b'PMID':
                arduino.write(bytes([b]))
                arduino.flush()
                time.sleep(0.01)
            station_serial_number = None
            for _ in range(60):
                if arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    if DEBUG:
                        print(f"[DEBUG] Received from {port}: {repr(line)}")
                    # Accept any serial message containing SNxxx or SNxxxx
                    match = re.search(r"SN\d{3,4}", line)
                    if match:
                        # Extract the full serial string if possible
                        serial_match = re.search(r"<SERIAL:([A-Z\-]*SN\d{3,4})>", line)
                        if serial_match:
                            station_serial_number = serial_match.group(1)
                        else:
                            station_serial_number = match.group(0)
                        if DEBUG:
                            print(f"[DEBUG] Station serial {station_serial_number} detected on {port}")
                        # Send CONFIRM_ID after any valid serial
                        arduino.write(config.CONFIRM_ID)
                        arduino.flush()
                        if DEBUG:
                            print(f"[DEBUG] Sent CONFIRM_ID to station on {port}")
                        break
                time.sleep(0.1)
            # Accept if detected serial is a substring of any entry in station_serials
            matched_entry = None
            if station_serial_number is not None:
                for entry in station_serials:
                    if station_serial_number in entry:
                        matched_entry = entry
                        break
            if matched_entry is None:
                if DEBUG:
                    print(f"[DEBUG] No recognized station detected on port {port}, skipping...")
                arduino.close()
                continue
            station_index = station_serials.index(matched_entry)
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

    print("[DEBUG] startup: checking E-STOP state...")
    while GPIO.input(config.E_STOP_PIN) == GPIO.LOW:
        time.sleep(0.1)
    print("[DEBUG] startup: E-STOP released, continuing startup.")

    print("[DEBUG] startup: creating StartupWizardDialog...")
    app = QApplication.instance() or QApplication(sys.argv)

    wizard = StartupWizardDialog(num_stations=NUM_STATIONS, bottle_ranges=bottle_ranges)
    print("[DEBUG] startup: StartupWizardDialog created")
    app.active_dialog = wizard

    print("[DEBUG] startup: setting station labels in wizard")
    wizard.set_station_labels(
        names=[f"Station {i+1}" for i in range(NUM_STATIONS)],
        connected=station_connected,
        enabled=station_enabled
    )

    print("[DEBUG] startup: showing station verification dialog")
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

    # --- 5. Calibration Step: Clear all scales ---
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
            selection_dialog.selected_index = 1  # Make 'BACK' the default selected option
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

    # --- 6. Filling mode selection dialog ---
    options = [
        ("AUTO", "Auto Mode"),
        ("MANUAL", "Manual Mode"),
        ("SMART", "Smart Mode")
    ]
    print("[DEBUG] Creating filling mode SelectionDialog...")
    print("[DEBUG] About to create SelectionDialog for filling mode...")

    try:
        selection_dialog = SelectionDialog(options=options, title="FILLING MODE")
        print(f"[DEBUG] SelectionDialog created: {selection_dialog}")
        selection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        print("[DEBUG] About to show SelectionDialog for filling mode...")
        try:
            selection_dialog.show()
            print("[DEBUG] SelectionDialog show() returned (should not crash before this)")
        except Exception as exc:
            print(f"[DEBUG] Exception during SelectionDialog show: {exc}")
            logging.error("Exception during SelectionDialog show", exc_info=True)
        app.active_dialog = selection_dialog

        filling_mode_selected = None
        def on_select(mode, index):
            print(f"[DEBUG] on_select called with mode={mode}, index={index}")
            nonlocal filling_mode_selected
            filling_mode_selected = mode
            try:
                filling_mode_callback(mode)
            except Exception as e:
                print(f"[DEBUG] Exception in filling_mode_callback: {e}")
            selection_dialog.accept()
            print("[DEBUG] SelectionDialog accepted.")
        selection_dialog.on_select_callback = on_select

        # Timeout logic: auto-select 'AUTO' after 5 seconds if no selection
        timeout_seconds = 5.0
        start_time = time.time()
        while selection_dialog.isVisible():
            app.processEvents()
            time.sleep(0.01)
            if time.time() - start_time > timeout_seconds:
                if filling_mode_selected is None:
                    print("[DEBUG] Timeout reached, auto-selecting 'AUTO' mode.")
                    filling_mode_selected = "AUTO"
                    filling_mode_callback("AUTO")
                    selection_dialog.accept()
        print("[DEBUG] SelectionDialog no longer visible.")
    except Exception as e:
        print(f"[DEBUG] Exception during filling mode dialog: {e}")
        logging.error(f"Exception during filling mode dialog: {e}")

    app.active_dialog = wizard

    # --- 7. If MANUAL, show info and go to RelayControlApp ---
    if filling_mode_selected == "MANUAL":
        info_dialog = InfoDialog(app.tr("Manual Mode Selected") if hasattr(app, 'tr') else "Manual Mode Selected", app.tr("Manual mode selected. You will control filling manually.") if hasattr(app, 'tr') else "Manual mode selected. You will control filling manually.", wizard)
        info_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        info_dialog.show()
        QTimer.singleShot(2500, info_dialog.accept)
        while info_dialog.isVisible():
            app.processEvents()
            time.sleep(0.01)
        wizard.finish_wizard()
        app.active_dialog = app
        after_startup()
        return

    # --- 8. Continue with calibration steps for AUTO/SMART ---
    # --- 7. Calibration Step: Place full bottles ---
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

        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        found = False
        for bottle_id, rng in full_ranges.items():
            if all(in_range(w, rng) for w in active_weights):
                selected_bottle_id = bottle_id
                found = True
                break

        if not found:
            dlg = InfoDialog(app.tr("Error") if hasattr(app, 'tr') else "Error", app.tr("All bottles must be within the same size range.") if hasattr(app, 'tr') else "All bottles must be within the same size range.", wizard)
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

    # --- 9. Calibration Step: Place empty bottles ---
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

        active_weights = [
            wizard.get_weight(i)
            for i in range(NUM_STATIONS)
            if station_enabled[i] and station_connected[i]
        ]

        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        if not all(in_range(w, bottle_ranges[selected_bottle_id]["empty"]) for w in active_weights):
            dlg = InfoDialog(app.tr("Error") if hasattr(app, 'tr') else "Error", app.tr("All bottles must be within the empty bottle weight range.") if hasattr(app, 'tr') else "All bottles must be within the empty bottle weight range.", wizard)
            ping_buzzer_invalid()
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.show()
            QTimer.singleShot(2000, dlg.accept)
            continue
        else:
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
"""

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
        # Clear serial buffer before handshake
        if arduino.in_waiting > 0:
            arduino.read(arduino.in_waiting)
        time.sleep(0.5)

        arduino.write(RESET_HANDSHAKE)
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
            # Ignore weight messages and only look for handshake response
            if arduino.in_waiting > 0:
                peek = arduino.read(1)
                if peek == b'<' or peek == b'S':
                    # Try to read a line for handshake
                    line = peek + arduino.read_until(b'\n')
                    try:
                        line_decoded = line.decode(errors='replace').strip()
                    except Exception:
                        line_decoded = str(line)
                    if DEBUG:
                        print(f"Received from {port}: {repr(line_decoded)}")
                    else:
                        logging.info(f"Received from {port}: {repr(line_decoded)}")
                    match = re.match(r"<SERIAL:(PM-SN\d{4})>", line_decoded)
                    if match:
                        station_serial_number = match.group(1)
                        if DEBUG:
                            print(f"Station serial {station_serial_number} detected on {port}")
                        else:
                            logging.info(f"Station serial {station_serial_number} detected on {port}")
                        break
                else:
                    # Ignore weight messages (binary data)
                    continue
            time.sleep(0.1)
        if station_serial_number is None or station_serial_number not in station_serials:
            if DEBUG:
                print(f"No recognized station detected on port {port}, skipping...")
            else:
                logging.error(f"No recognized station detected on port {port}, skipping...")
            arduino.close()
            return False

        station_index = station_serials.index(station_serial_number)

        arduino.write(CONFIRM_ID)
        arduino.flush()
        if DEBUG:
            print(f"Sent CONFIRM_ID to station {station_index+1} on {port}")
        else:
            logging.info(f"Sent CONFIRM_ID to station {station_index+1} on {port}")

        got_request = False
        for _ in range(40):
            if arduino.in_waiting > 0:
                req = arduino.read(1)
                if req == REQUEST_CALIBRATION:
                    if DEBUG:
                        print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                    else:
                        logging.info(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
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
        active_dialog = getattr(app, "active_dialog", None)
        filling_mode = getattr(app, "filling_mode", "AUTO")
        overlay_widget = getattr(app, "overlay_widget", None)
        refresh_ui = getattr(app, "refresh_ui", None)

        # --- Unified station_widgets selection ---
        if active_dialog and hasattr(active_dialog, "station_widgets"):
            station_widgets = active_dialog.station_widgets
        else:
            station_widgets = getattr(app, "station_widgets", None)

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
                port = arduino_ports[station_index]
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
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"UP button pressed, dialog: {dialog}")
            flash_dialog_icon(0)
            if hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("up")
            while GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            dialog.select_prev()
            if hasattr(dialog, "set_arrow_inactive"):
                dialog.set_arrow_inactive("up")
            return

        # DOWN BUTTON
        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"DOWN button pressed, dialog: {dialog}")
            flash_dialog_icon(2)
            if hasattr(dialog, "set_arrow_active"):
                dialog.set_arrow_active("down")
            while GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            dialog.select_next()
            if hasattr(dialog, "set_arrow_inactive"):
                dialog.set_arrow_inactive("down")
            return

        # SELECT BUTTON
        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            print(f"SELECT button pressed, dialog: {dialog}")
            flash_dialog_icon(1)
            while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
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
            GPIO.output(RELAY_POWER_PIN, GPIO.HIGH)
            RELAY_POWER_ENABLED = True  # Set flag after relay power is enabled

            app.active_dialog = app
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

    wizard = StartupWizardDialog(num_stations=NUM_STATIONS)
    app_qt.active_dialog = wizard  # Set wizard as active dialog for button handling
    context = {
            'wizard': wizard,
            'app': app_qt,
            'NUM_STATIONS': NUM_STATIONS,
            'station_enabled': station_enabled,
            'station_connected': station_connected,
            'arduinos': arduinos,
            'config': config,
            'SelectionDialog': SelectionDialog,
            'InfoDialog': InfoDialog,
            'Qt': Qt,
            'QTimer': QTimer,
            'logging': logging,
            'config_file': config_file,
            'filling_mode_callback': filling_mode_callback,
            'ping_buzzer_invalid': ping_buzzer_invalid,
            'after_startup': after_startup
        }

    run_startup_sequence(context)

    app_qt.exec()


if __name__ == "__main__":
    main()