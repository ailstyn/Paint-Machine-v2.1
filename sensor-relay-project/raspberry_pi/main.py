import os
import serial
import time
import logging
import RPi.GPIO as GPIO
from gui.gui import RelayControlApp, MenuDialog
from gui.languages import LANGUAGES
import sys
import signal
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import re


# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure log directory exists
log_filename = os.path.join(LOG_DIR, f"error_log_{datetime.now().strftime('%Y-%m-%d')}.txt")
logging.basicConfig(
    filename=log_filename,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.error("Test error: logging is working.")

# List of potential serial ports for the Arduinos
arduino_ports = [
    '/dev/ttyACM0',  # Adjust these ports as needed
    '/dev/ttyACM1',
    '/dev/ttyACM2',
    '/dev/ttyACM3'
]

# Shared variables
target_weight = 500.0  # Example target weight in grams
time_limit = 3000  # Example time limit in milliseconds
config_file = "config.txt"  # File to store scale calibration values
scale_calibrations = []  # List to hold calibration values

# Byte-based protocol for communication
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

# GPIO pin assignments for buttons
UP_BUTTON_PIN = 5
DOWN_BUTTON_PIN = 6
SELECT_BUTTON_PIN = 16
E_STOP_PIN = 23
BUZZER_PIN = 26
RELAY_POWER_PIN = 17

# Add a global flag for E-Stop
E_STOP = False
PREV_E_STOP_STATE = GPIO.HIGH
FILL_LOCKED = False

last_fill_time = None
last_final_weight = None
fill_time_limit_reached = False

# Usage example:
NUM_STATIONS = 4  # Set this to however many stations you have
arduinos = [None] * NUM_STATIONS

# Replace your old load/write functions with these:
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
                    # Extract station number (1-based)
                    station_num = int(key.replace("station", "").replace("_calibration", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        calibrations[station_num - 1] = float(value)
    except FileNotFoundError:
        logging.error(f"{config_file} not found. Using default calibration values.")
    except Exception as e:
        logging.error(f"Error reading {config_file}: {e}")
    scale_calibrations = calibrations
    print(f"Loaded scale calibration values: {scale_calibrations}")

def write_scale_calibrations():
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    # Read existing config
    try:
        with open(config_path, "r") as file:
            lines = file.readlines()
    except FileNotFoundError:
        lines = []

    # Remove old calibration lines
    lines = [line for line in lines if not (line.startswith("station") and "_calibration=" in line)]

    # Add new calibration lines
    for idx, value in enumerate(scale_calibrations):
        lines.append(f"station{idx+1}_calibration={value}\n")

    # Write back to config
    with open(config_path, "w") as file:
        file.writelines(lines)

def calibrate_scale(arduino_id, app):
    try:
        arduino = arduinos[arduino_id]
        print(f"[calibrate_scale] Starting calibration for Arduino {arduino_id}")

        arduino.write(RESET_CALIBRATION)
        arduino.flush()
        print("[calibrate_scale] Sent RESET_CALIBRATION to Arduino")

        # Step 1: Remove all weight from the scale
        app.show_dialog_content(
            title=LANGUAGES[app.language]["CALIBRATION_TITLE"],
            message=LANGUAGES[app.language]["CALIBRATION_REMOVE_WEIGHT"]
        )
        print("[calibrate_scale] Step 1 dialog shown")

        while True:
            # Read current weight from Arduino
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CURRENT_WEIGHT:
                    try:
                        weight_line = arduino.readline().decode('utf-8', errors='replace').strip()
                        weight = float(weight_line)
                        app.set_current_weight_mode(weight)
                    except Exception as e:
                        logging.error(f"[calibrate_scale] Error parsing weight: {e}")
                        print(f"[calibrate_scale] Error parsing weight: {e}")

            # Check for SELECT button press
            if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                ping_buzzer()
                print("[calibrate_scale] SELECT pressed in Step 1")
                # Wait for button release to avoid double press
                while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                    QApplication.processEvents()
                    time.sleep(0.01)
                # Send CALIBRATION_CONTINUE to Arduino
                clear_serial_buffer(arduino)
                arduino.write(CALIBRATION_CONTINUE)
                arduino.flush()
                print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino")
                break

        # Wait for CALIBRATION_STEP_DONE from Arduino before proceeding to Step 2
        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE from Arduino")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE from Arduino")
                    break
            QApplication.processEvents()
            time.sleep(0.01)

        # --- Step 2: Place calibration weight and set value ---
        calib_weight = 100  # Default value in grams

        def update_display(value, *args, **kwargs):
            app.show_dialog_content(
                title=f"Calibration (Arduino {arduino_id+1})",
                message=LANGUAGES[app.language]["CALIBRATION_PLACE_WEIGHT"].format(value=value)
            )

        print("[calibrate_scale] Step 2 dialog shown")
        update_display(calib_weight)

        calib_weight = adjust_value_with_acceleration(
            initial_value=calib_weight,
            dialog=type('DialogStub', (), {
                'update_value': staticmethod(update_display),
                'accept': staticmethod(lambda *args, **kwargs: None),
                'close': staticmethod(lambda *args, **kwargs: None)
            })(),
            up_button_pin=UP_BUTTON_PIN,
            down_button_pin=DOWN_BUTTON_PIN,
            unit_increment=1,
            min_value=0,
            up_callback=update_display,
            down_callback=update_display
        )
        print(f"[calibrate_scale] Calibration weight set to {calib_weight}")

        # Wait for SELECT button press in Step 2
        while True:
            QApplication.processEvents()
            time.sleep(0.01)
            if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                ping_buzzer()
                print("[calibrate_scale] SELECT pressed in Step 2")
                # Wait for button release to avoid double press
                while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                    QApplication.processEvents()
                    time.sleep(0.01)
                # Send CALIBRATION_WEIGHT byte and value to Arduino
                arduino.write(CALIBRATION_WEIGHT)
                arduino.write(f"{calib_weight}\n".encode('utf-8'))
                print(f"[calibrate_scale] Sent CALIBRATION_WEIGHT and value {calib_weight} to Arduino")
                break

        # Wait for CALIBRATION_STEP_DONE from Arduino before proceeding
        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE after sending weight")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE after sending weight")
                    break
            QApplication.processEvents()
            time.sleep(0.01)

        # Send CALIBRATION_CONTINUE to Arduino to proceed to the next step
        arduino.write(CALIBRATION_CONTINUE)
        print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino for Step 3")

        # --- Step 3: Wait for calibration value from Arduino ---
        app.show_dialog_content(
            title=f"Calibration (Arduino {arduino_id+1})",
            message=LANGUAGES[app.language]["CALIBRATION_CALCULATING"]
        )
        print("[calibrate_scale] Step 3 dialog shown, waiting for CALIBRATION_WEIGHT from Arduino")

        new_calibration = None
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_WEIGHT:
                    # Read the calibration value sent as a string (e.g., "427.53\n")
                    try:
                        calib_line = arduino.readline().decode('utf-8', errors='replace').strip()
                        new_calibration = float(calib_line)
                        print(f"[calibrate_scale] Received new calibration value: {new_calibration}")
                        break
                    except Exception as e:
                        logging.error(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")
                        print(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")
            QApplication.processEvents()
            time.sleep(0.01)

        # Save the new calibration value for this Arduino
        scale_calibrations[arduino_id] = new_calibration
        print(f"[calibrate_scale] Saving calibration value {new_calibration} for Arduino {arduino_id}")
        write_scale_calibrations()

        # Confirmation dialog
        app.show_dialog_content(
            title=LANGUAGES[app.language]["CALIBRATION_COMPLETE_TITLE"],
            message=LANGUAGES[app.language]["CALIBRATION_COMPLETE_MSG"].format(value=new_calibration)
        )
        print("[calibrate_scale] Calibration complete dialog shown")
        # Wait for SELECT to finish
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
            QApplication.processEvents()
            time.sleep(0.01)
        ping_buzzer()
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            QApplication.processEvents()
            time.sleep(0.01)

        app.clear_dialog_content()
        print("[calibrate_scale] Calibration process finished and UI reset")

    except Exception as e:
        logging.error(f"[calibrate_scale] Unexpected error: {e}")
        print(f"[calibrate_scale] Unexpected error: {e}")
        
def tare_scale(arduino_id):
#     arduino_id: The ID of the Arduino to send the tare command to.

    if arduino_id < 0 or arduino_id >= len(arduinos):
        logging.error(f"Invalid Arduino ID: {arduino_id}")
        return

    try:
        arduino = arduinos[arduino_id]
        arduino.write(TARE_SCALE)  # Send the tare command
        print(f"Sent TARE_SCALE command to Arduino {arduino_id}")
    except serial.SerialException as e:
        logging.error(f"Error communicating with Arduino {arduino_id}: {e}")


def setup_gpio():
    try:
        GPIO.setwarnings(False)
        GPIO.cleanup()  # Reset any previous state
        print('setting up GPIO')
        GPIO.setmode(GPIO.BCM)
        print('set mode BCM')
        GPIO.setup(UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print('up button pin set')
        GPIO.setup(DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print('down button pin set')
        GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        print('select button pin set')
        GPIO.setup(E_STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        print('setting up relay power control')
        GPIO.setup(RELAY_POWER_PIN, GPIO.OUT)
    except Exception as e:
        logging.error(f"Error in setup_gpio: {e}")


def ping_buzzer(duration=0.05):
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def ping_buzzer_invalid():
    # Simulate a lower pitch by making a longer beep or double beep
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(BUZZER_PIN, GPIO.LOW)
    time.sleep(0.05)
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(0.15)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def handle_button_presses(app):
    try:
        dialog = getattr(app, "active_dialog", None)

        # UP BUTTON
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            # Wait for release
            while GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_prev()
            return

        # DOWN BUTTON
        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
            while GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            if dialog is not None:
                dialog.select_next()
            return

        # SELECT BUTTON
        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer()
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

def startup():
    global arduinos
    arduinos = [None] * NUM_STATIONS
    for port in arduino_ports:
        try:
            arduino = serial.Serial(port, 9600, timeout=0.1)
            arduino.reset_input_buffer()
            found_id = False
            loop_count = 0
            # Only try to connect if any station is enabled and not already assigned
            while not found_id and loop_count < 100:
            # Every 10 loops, resend GET_ID
                if loop_count % 10 == 0:
                    arduino.reset_input_buffer()
                    arduino.write(GET_ID)
                    arduino.flush()
                    time.sleep(0.05)
            # Read all available bytes and look for a line with <ID:...>
                while arduino.in_waiting > 0:
                    line = arduino.read_until(b'\n').decode(errors='replace').strip()
                    print(f"Raw station ID response: {repr(line)}")
                    match = re.match(r"<ID:(\d+)>", line)
                    if match:
                        station_id = int(match.group(1))
                        print(f"Arduino reports station ID {station_id}")
                        # Only connect if this station is enabled
                        if 1 <= station_id <= NUM_STATIONS and station_enabled[station_id - 1]:
                            arduinos[station_id - 1] = arduino
                            found_id = True
                            print(f"Connected to enabled station {station_id} on {port}")
                            break
                        else:
                            print(f"Station {station_id} is disabled or invalid, skipping.")
                loop_count += 1
                time.sleep(0.05)
            if not found_id:
                print(f"Failed to get enabled station ID from {port} after retries.")
                arduino.close()
        except Exception as e:
            msg = f"Port {port} not available or failed: {e}"
            print(msg)
            logging.error(msg)

    if not arduinos:
        print("No Arduinos connected. Exiting program.")
        exit(1)  # Exit if no Arduinos are connected


def adjust_value_with_acceleration(
    initial_value, 
    dialog, 
    up_button_pin, 
    down_button_pin, 
    unit_increment=1, 
    min_value=0, 
    up_callback=None, 
    down_callback=None
):
    value = initial_value
    DEBOUNCE = 0.01  # seconds for polling
    while True:
        # UP BUTTON
        if GPIO.input(up_button_pin) == GPIO.LOW:
            start_time = time.time()
            repeats = 0
            interval = 0.125
            while GPIO.input(up_button_pin) == GPIO.LOW:
                elapsed = time.time() - start_time
                # Each interval lasts 1 second before jumping to the next
                if elapsed >= 4:
                    interval = 1 / 64  # 64 times per second
                elif elapsed >= 3:
                    interval = 1 / 32  # 32 times per second
                elif elapsed >= 2:
                    interval = 1 / 16  # 16 times per second
                elif elapsed >= 1:
                    interval = 1 / 8   # 8 times per second
                else:
                    interval = 1 / 8   # Start at 8 times per second

                value += unit_increment
                if up_callback:
                    up_callback(value)
                dialog.update_value(value)
                ping_buzzer(0.05)
                repeats += 1
                # Wait for interval or until button released
                for _ in range(int(interval / DEBOUNCE)):
                    if GPIO.input(up_button_pin) == GPIO.HIGH:
                        break
                    QApplication.processEvents()
                    time.sleep(DEBOUNCE)
            continue  # Skip to next loop to avoid double-processing

        # DOWN BUTTON
        if GPIO.input(down_button_pin) == GPIO.LOW:
            start_time = time.time()
            repeats = 0
            interval = 0.125
            while GPIO.input(down_button_pin) == GPIO.LOW:
                elapsed = time.time() - start_time
                if elapsed >= 4:
                    interval = 1 / 64
                elif elapsed >= 3:
                    interval = 1 / 32
                elif elapsed >= 2:
                    interval = 1 / 16
                elif elapsed >= 1:
                    interval = 1 / 8
                else:
                    interval = 1 / 8
                if value - unit_increment >= min_value:
                    value -= unit_increment
                    if down_callback:
                        down_callback(value)
                    dialog.update_value(value)
                    ping_buzzer(0.05)
                else:
                    ping_buzzer_invalid()
                repeats += 1
                for _ in range(int(interval / DEBOUNCE)):
                    if GPIO.input(down_button_pin) == GPIO.HIGH:
                        break
                    QApplication.processEvents()
                    time.sleep(DEBOUNCE)
            continue

        # SELECT BUTTON
        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            ping_buzzer(0.05)
            while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
            dialog.accept()
            break

        QApplication.processEvents()
        time.sleep(DEBOUNCE)
    dialog.close()
    return value

def clear_serial_buffer(arduino):
    """Read and discard all available bytes from the Arduino serial buffer."""
    while arduino.in_waiting > 0:
        arduino.read(arduino.in_waiting)

def load_station_enabled_flags():
    """Load enabled/disabled flags for each station from config.txt."""
    enabled = [False] * NUM_STATIONS
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, "r") as file:
            for line in file:
                if line.startswith("station") and "_enabled=" in line:
                    key, value = line.strip().split("=")
                    station_num = int(key.replace("station", "").replace("_enabled", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        enabled[station_num - 1] = value.lower() == "true"
    except Exception as e:
        logging.error(f"Error reading enabled flags: {e}")
    return enabled

def poll_hardware(app):
    global E_STOP, last_fill_time, last_final_weight, fill_time_limit_reached, E_STOP_ACTIVATED, target_weight
    try:
        for station_index, arduino in enumerate(arduinos):
            if arduino is None:
                continue
            if not station_enabled[station_index]:
                continue  # Skip disabled stations

            estop_pressed = GPIO.input(E_STOP_PIN) == GPIO.LOW
            if estop_pressed:
                print(f"Station {station_index+1}: E-STOP pressed")
                if not E_STOP:
                    E_STOP = True
                    app.overlay_widget.show_overlay(
                        f"<span style='font-size:80px; font-weight:bold;'>E-STOP</span><br>"
                        f"<span style='font-size:40px;'>Emergency Stop Activated</span>",
                        color="#CD0A0A"
                    )
                while arduino.in_waiting > 0:
                    print(f"Station {station_index+1}: Flushing serial buffer due to E-STOP")
                    arduino.read(arduino.in_waiting)
                    arduino.write(E_STOP_ACTIVATED)
                continue

            if E_STOP:
                print("E-STOP cleared")
                E_STOP = False
                app.overlay_widget.hide_overlay()

            # Normal operation for this station
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
                    # Try to read the rest of the line for context
                    if arduino.in_waiting > 0:
                        extra = arduino.readline().decode('utf-8', errors='replace').strip()
                        print(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
                    else:
                        print(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
                        app.refresh_ui()
    except Exception as e:
        logging.error(f"Error in poll_hardware: {e}")
        print(f"Error in poll_hardware: {e}")

# At startup, load enabled flags:
station_enabled = load_station_enabled_flags()

# In your main loop, poll all stations:
def main():
    try:
        logging.info("Starting main application.")
        load_scale_calibrations()
        global station_enabled
        station_enabled = load_station_enabled_flags()
        setup_gpio()
        startup()  # Initialize serial connections

        # Create QApplication before any QWidget
        app_qt = QApplication(sys.argv)

        app = RelayControlApp()
        app.set_calibrate = calibrate_scale

        # Set the GUI's target weight to match your default
        app.target_weight = target_weight  # <-- Add this line

        print('app initialized, contacting arduinos')

        # Set offline state for disabled stations
        bg_colors_deactivated = ["#401010", "#131c35", "#041B04", "#3c3a15"]
        for i, widget in enumerate(app.station_widgets):
            if not station_enabled[i]:
                widget.set_offline(bg_colors_deactivated[i])
            if station_enabled[i]:
                widget.set_weight(0, target_weight)

        GPIO.output(RELAY_POWER_PIN, GPIO.HIGH)  # Power on the relays
        # Make Ctrl+C work with PyQt event loop
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Use QTimer for polling instead of while True
        timer = QTimer()
        timer.timeout.connect(lambda: poll_hardware(app))
        timer.start(35)  # 35 ms interval

        # Use QTimer for polling GPIO buttons
        button_timer = QTimer()
        button_timer.timeout.connect(lambda: handle_button_presses(app))
        button_timer.start(50)  # 50 ms interval

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

# Uncaught exception logging
def log_uncaught_exceptions(exctype, value, tb):
    logging.error("Uncaught exception", exc_info=(exctype, value, tb))
    print("Uncaught exception:", value)

sys.excepthook = log_uncaught_exceptions

if __name__ == "__main__":
    main()