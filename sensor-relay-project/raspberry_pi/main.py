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
from startup import prestartup_steps
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


# ========== BUTTON DELAY VARIABLE ========== 
## BUTTON_DELAY is now managed in config.py

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
    # ...existing code...
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

        # --- E-STOP dialog management ---
        if not hasattr(app, '_prev_active_dialog'):
            app._prev_active_dialog = None

        # Handle E-STOP state change
        if estop_pressed and not E_STOP:
            if DEBUG:
                print("E-STOP pressed")
            E_STOP = True
            FILL_LOCKED = True
            # Save current active dialog before E-STOP
            app._prev_active_dialog = getattr(app, 'active_dialog', None)
            if active_dialog is not None:
                try:
                    active_dialog.reject()
                except Exception as e:
                    logging.error(f"Error rejecting active dialog: {e}")
            # Show overlay and set as active dialog
            if overlay_widget:
                overlay_widget.show_overlay(
                    f"<span style='font-size:80px; font-weight:bold;'>E-STOP</span><br>"
                    f"<span style='font-size:40px;'>Emergency Stop Activated</span>",
                    color="#CD0A0A"
                )
                app.active_dialog = overlay_widget
            for arduino in arduinos:
                if arduino:
                    arduino.write(E_STOP_ACTIVATED)
                    arduino.flush()
        elif not estop_pressed and E_STOP:
            if DEBUG:
                print("E-STOP released")
            E_STOP = False
            FILL_LOCKED = False
            # Hide overlay and restore previous active dialog
            if overlay_widget:
                overlay_widget.hide_overlay()
            if hasattr(app, '_prev_active_dialog') and app._prev_active_dialog is not None:
                app.active_dialog = app._prev_active_dialog
            app._prev_active_dialog = None

        for station_index, arduino in enumerate(arduinos):
            # ...existing code...
            if arduino is None or not station_enabled[station_index]:
                continue
            try:
                if E_STOP:
                    while arduino.in_waiting > 0:
                        arduino.read(arduino.in_waiting)
                    continue

                # ...existing code...

                while arduino.in_waiting > 0:
                    message_type = arduino.read(1)
                    # ...existing code...
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
def button_delay():
    # Deprecated: replaced by QTimer-based debounce
    return False

def handle_button_presses(app):
    global DEBUG
    try:
        dialog = getattr(app, "active_dialog", None)
        if dialog is None:
            error_msg = "ERROR: No active dialog! Button press ignored."
            print(error_msg)
            logging.error(error_msg)
            return

        def flash_dialog_icon(index):
            if dialog is not None and hasattr(dialog, "button_column"):
                dialog.button_column.flash_icon(index)
            elif hasattr(app, "button_column"):
                app.button_column.flash_icon(index)

        def pause_button_polling():
            # Pause the button polling timer for BUTTON_DELAY ms
            if hasattr(app, "button_timer"):
                app.button_timer.stop()
                QTimer.singleShot(config.BUTTON_DELAY, app.button_timer.start)

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
            pause_button_polling()
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
            pause_button_polling()
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
            pause_button_polling()
            return

    except Exception as e:
        logging.error("Error in handle_button_presses", exc_info=True)
        if DEBUG:
            print(f"Error in handle_button_presses: {e}")

# ========== MAIN ENTRY POINT ==========

def main():
    global arduinos, station_connected
    try:
        print("[DEBUG] main() started")
        logging.info("Starting main application.")
        load_scale_calibrations()
        print("[DEBUG] load_scale_calibrations() complete")
        global station_enabled
        config_path = "config.txt"
        station_enabled = load_station_enabled(config_path)
        print(f"[DEBUG] Loaded station_enabled: {station_enabled}")
        setup_gpio()
        print("[DEBUG] setup_gpio() complete")

        app_qt = QApplication(sys.argv)
        print("[DEBUG] QApplication created")

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        print("[DEBUG] signal handler set")

        timer = QTimer()
        button_timer = QTimer()
        app_qt.button_timer = button_timer  # Attach timer to app for pause access
        button_timer.timeout.connect(lambda: handle_button_presses(app_qt))
        button_timer.start(50)
        print("[DEBUG] button_timer started")

        # Start poll_hardware BEFORE startup
        timer.timeout.connect(lambda: poll_hardware(app_qt))
        timer.start(35)
        print("[DEBUG] poll_hardware timer started")

        def after_startup():
            print("[DEBUG] after_startup() called")
            global RELAY_POWER_ENABLED
            app = RelayControlApp(
                station_enabled=station_enabled,
                filling_mode_callback=filling_mode_callback
            )
            app.set_calibrate = None
            # Always update target_weight and time_limit from globals after startup
            app.target_weight = target_weight
            app.time_limit = time_limit
            print(f"[DEBUG] after_startup: app.target_weight set to {app.target_weight}, app.time_limit set to {app.time_limit}")
            app.filling_mode = filling_mode  # Ensure filling_mode is set

            for i, widget in enumerate(app.station_widgets):
                if station_enabled[i]:
                    widget.set_weight(0, target_weight, "g")

            timer.timeout.disconnect()
            timer.timeout.connect(lambda: poll_hardware(app))
            button_timer.timeout.disconnect()
            button_timer.timeout.connect(lambda: handle_button_presses(app))
            app.button_timer = button_timer  # Attach timer to app for pause access
            app.show()
            GPIO.output(RELAY_POWER_PIN, GPIO.HIGH)
            config.RELAY_POWER_ENABLED = True  # Set flag after relay power is enabled

            config.BUTTON_DELAY = 50  # Set button delay to 0.05s after startup
            app.active_dialog = app
            print("[DEBUG] after_startup() finished")

        print("[DEBUG] Creating StartupWizardDialog...")
        wizard = StartupWizardDialog(num_stations=NUM_STATIONS)
        print("[DEBUG] StartupWizardDialog created")
        app_qt.active_dialog = wizard  # Set wizard as active dialog for button handling
        print("[DEBUG] app_qt.active_dialog set to wizard")
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
        print("[DEBUG] context built")

        # Run prestartup steps to initialize serials and arduinos
        for step_func in prestartup_steps:
            print(f"[DEBUG] Running prestartup step: {step_func.__name__}")
            result = step_func(context)
            print(f"[DEBUG] Prestartup step {step_func.__name__} returned: {result}")

        # Update global variables from context before main startup
        if 'arduinos' in context:
            arduinos = context['arduinos']
            print(f"[DEBUG] Updated global arduinos: {arduinos}")
        if 'station_connected' in context:
            station_connected = context['station_connected']
            print(f"[DEBUG] Updated global station_connected: {station_connected}")

        # Now run the main startup sequence
        print("[DEBUG] Running startup sequence...")
        run_startup_sequence(context)
        print("[DEBUG] startup sequence complete")
        # Debug: print context values after startup
        print(f"[DEBUG] Context after startup: target_weight={context.get('target_weight')}, time_limit={context.get('time_limit')}")
        # Set target_weight and time_limit from context after startup
        if 'target_weight' in context and context['target_weight'] is not None:
            global target_weight
            target_weight = context['target_weight']
            print(f"[DEBUG] Set target_weight to {target_weight}")
        else:
            print("[DEBUG] target_weight not set in context after startup")
        if 'time_limit' in context and context['time_limit'] is not None:
            global time_limit
            time_limit = context['time_limit']
            print(f"[DEBUG] Set time_limit to {time_limit}")
        else:
            print("[DEBUG] time_limit not set in context after startup")

        print("[DEBUG] Entering app_qt.exec() event loop")
        app_qt.exec()
        print("[DEBUG] app_qt.exec() finished")

    except KeyboardInterrupt:
        print("[DEBUG] Program interrupted by user.")
        logging.info("Program interrupted by user.")
    except Exception as e:
        print(f"[DEBUG] Exception in main(): {e}")
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        print("[DEBUG] Shutting down...")
        logging.info("Shutting down and cleaning up GPIO.")
        GPIO.cleanup()

if __name__ == "__main__":
    main()