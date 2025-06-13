import os
import serial
import time
import logging
import RPi.GPIO as GPIO
from gui.gui import RelayControlApp
from gui.languages import LANGUAGES
import sys
import signal
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer


# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure log directory exists
log_filename = os.path.join(LOG_DIR, f"error_log_{datetime.now().strftime('%Y-%m-%d')}.txt")
logging.basicConfig(
    filename=log_filename,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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

# Add a global flag for E-Stop
E_STOP = False
PREV_E_STOP_STATE = GPIO.HIGH
FILL_LOCKED = False

last_fill_time = None
last_final_weight = None
fill_time_limit_reached = False

# Usage example:
NUM_STATIONS = 4  # Set this to however many stations you have

# Create a list of active serial connections
arduinos = [None] * NUM_STATIONS
for port in arduino_ports:
    try:
        arduino = serial.Serial(port, 9600, timeout=1)
        for attempt in range(5):
            arduino.reset_input_buffer()
            arduino.write(GET_ID)
            time.sleep(0.2)
            if arduino.in_waiting > 0:
                response = arduino.readline().decode(errors='replace').strip()
                print(f"Raw station ID response from {port}: {repr(response)}")
                try:
                    station_id = int(response)
                    print(f"Arduino on {port} reports station ID {station_id}")
                    if 1 <= station_id <= NUM_STATIONS:
                        arduinos[station_id - 1] = arduino
                        break  # Success!
                    else:
                        print(f"Invalid station ID {station_id} from {port}")
                except ValueError:
                    print(f"Could not parse station ID from {port}: {repr(response)}")
            else:
                print(f"No station ID response from {port}, retrying...")
                time.sleep(0.5)
        else:
            print(f"Failed to get station ID from {port} after retries.")
    except Exception as e:
        print(f"Port {port} not available or failed: {e}")

if not arduinos:
    print("No Arduinos connected. Exiting program.")
    exit(1)  # Exit if no Arduinos are connected

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
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
            if hasattr(app, "menu_dialog") and app.menu_dialog and app.menu_dialog.isVisible():
                app.menu_dialog.select_prev()
            else:
                print("UP button pressed")
                if app.selected_index > 0:
                    app.update_selection_dot(app.selected_index - 1)  # Move dot first
                    ping_buzzer()
                else:
                    ping_buzzer_invalid()
            # Replace blocking sleep with a short polling debounce
            for _ in range(20):  # ~0.2s if DEBOUNCE=0.01
                QApplication.processEvents()
                time.sleep(0.01)
        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
            if hasattr(app, "menu_dialog") and app.menu_dialog and app.menu_dialog.isVisible():
                app.menu_dialog.select_next()
            else:
                print("DOWN button pressed")
                if app.selected_index < len(app.dot_widgets) - 1:
                    app.update_selection_dot(app.selected_index + 1)
                    ping_buzzer()
                else:
                    ping_buzzer_invalid()
            for _ in range(20):
                QApplication.processEvents()
                time.sleep(0.01)
        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            print(f"SELECT button pressed at index {app.selected_index}")
            ping_buzzer()
            while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                QApplication.processEvents()
                time.sleep(0.01)
            # If menu is open, activate selected item
            if hasattr(app, "menu_dialog") and app.menu_dialog and app.menu_dialog.isVisible():
                app.menu_dialog.activate_selected()
                print("Menu item activated")
            else:
                app.show_menu()
                print("Menu opened")
            time.sleep(0.1)
    except Exception as e:
        logging.error(f"Error in handle_button_presses: {e}")

def startup(app):
    # Display the "CLEAR SCALES" message
    app.display_message(LANGUAGES[app.language]["CLEAR_SCALES_TITLE"], LANGUAGES[app.language]["CLEAR_SCALES_MSG"])

    # Wait for the select button to be pressed
    print("Waiting for SELECT button to be pressed...")
    while GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:  # Wait until the button is pressed (LOW)
        time.sleep(0.1)

    print("SELECT button pressed. Proceeding with startup.")

    # Send the TARE_SCALE command to every connected Arduino
    for i, arduino in enumerate(arduinos):
        try:
            arduino.write(TARE_SCALE)  # Send the tare command
            print(f"Sent TARE_SCALE command to Arduino {i} on port {arduino.port}")
        except serial.SerialException as e:
            logging.error(f"Error sending TARE_SCALE to Arduino {i} on port {arduino.port}: {e}")

    # Display the "SCALES RESET" message
    app.display_message(LANGUAGES[app.language]["SCALES_RESET_TITLE"], LANGUAGES[app.language]["SCALES_RESET_MSG"])
    time.sleep(3)  # Wait for 3 seconds

    # Reload the main screen
    app.reload_main_screen()

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

# Usage in set_target_weight:
def set_target_weight(app):
    global target_weight

    def update_display(value, *args, **kwargs):
        lang = getattr(app, "language", "en")
        if getattr(app, "display_unit", "g") == "oz":
            shown_value = round(value, 1)
            unit = "oz"
        else:
            shown_value = value
            unit = "g"
        app.show_dialog_content(
            title=LANGUAGES[app.language]["SET_TARGET_WEIGHT_TITLE"],
            message=f"{shown_value} {unit}\n\n{LANGUAGES[app.language]['SET_TARGET_WEIGHT_MSG']}",
        )

    # Convert the initial value to the display unit for editing
    if getattr(app, "display_unit", "g") == "oz":
        initial_value = round(target_weight * 0.03527, 1)
        unit_increment = 0.1
    else:
        initial_value = target_weight
        unit_increment = 1

    update_display(initial_value)
    
    # Adjust in the display unit, but always save in grams
    adjusted_value = adjust_value_with_acceleration(
        initial_value=initial_value,
        dialog=type('DialogStub', (), {
            'update_value': staticmethod(update_display),
            'accept': staticmethod(lambda *args, **kwargs: None),
            'close': staticmethod(lambda *args, **kwargs: None)
        })(),
        up_button_pin=UP_BUTTON_PIN,
        down_button_pin=DOWN_BUTTON_PIN,
        unit_increment=unit_increment,
        min_value=0,
        up_callback=update_display,
        down_callback=update_display
    )

    # Convert back to grams if needed
    if getattr(app, "display_unit", "g") == "oz":
        target_weight = adjusted_value / 0.03527
    else:
        target_weight = adjusted_value

    clear_serial_buffer(arduinos[0])
    app.clear_dialog_content()

# Usage in set_time_limit:
def set_time_limit(app):
    global time_limit

    def update_display(value, *args, **kwargs):
        seconds = value / 1000.0
        app.show_dialog_content(
            title=LANGUAGES[app.language]["SET_TIME_LIMIT_TITLE"],
            message=f"{seconds:.1f} s\n\n{LANGUAGES[app.language]['SET_TIME_LIMIT_MSG']}",
        )

    # Show the initial value immediately
    update_display(time_limit)

    time_limit = adjust_value_with_acceleration(
        initial_value=time_limit,
        dialog=type('DialogStub', (), {
            'update_value': staticmethod(update_display),
            'accept': staticmethod(lambda *args, **kwargs: None),
            'close': staticmethod(lambda *args, **kwargs: None)
        })(),
        up_button_pin=UP_BUTTON_PIN,
        down_button_pin=DOWN_BUTTON_PIN,
        unit_increment=100,
        min_value=0,
        up_callback=update_display,
        down_callback=update_display
    )
    clear_serial_buffer(arduinos[0])
    app.clear_dialog_content()

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
            # print(f"Polling station {station_index+1} (enabled, Arduino connected)")

            # print(f"Station {station_index+1}: Arduino in_waiting = {arduino.in_waiting}")
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
                # print(f"Station {station_index+1}: Reading message type...")
                message_type = arduino.read(1)
                # print(f"Station {station_index+1}: Received message_type: {message_type}")
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
                    #print(f"Station {station_index+1}: CURRENT_WEIGHT")
                    current_weight = arduino.readline().decode('utf-8').strip()
                    #print(f"Station {station_index+1} CURRENT_WEIGHT raw: '{current_weight}'")
                    try:
                        weight = float(current_weight)
                        if weight < 0:
                            weight = 0.0
                        app.update_station_weight(station_index, weight)
                    except Exception as e:
                        logging.error(f"Invalid weight value for station {station_index}: {current_weight} ({e})")
                        app.update_station_weight(station_index, 0.0)
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

        # Create QApplication before any QWidget
        app_qt = QApplication(sys.argv)

        app = RelayControlApp()
        app.set_target_weight = set_target_weight
        app.set_time_limit = set_time_limit
        app.set_calibrate = calibrate_scale

        # Set the GUI's target weight to match your default
        app.target_weight = target_weight  # <-- Add this line

        print('app initialized, contacting arduinos')

        # Set offline state for disabled stations
        bg_colors_deactivated = ["#6c2222", "#22305a", "#2b4d2b", "#b1a93a"]
        for i, widget in enumerate(app.station_widgets):
            if not station_enabled[i]:
                widget.set_offline(bg_colors_deactivated[i])
            if station_enabled[i]:
                widget.set_weight(0, target_weight)

        for arduino in arduinos:
            if arduino is not None:
                arduino.reset_input_buffer()
                arduino.reset_output_buffer()
                try:
                    arduino.write(b'P')
                    print(f"Sent 'P' (PI READY) to Arduino on {arduino.port}")
                except Exception as e:
                    logging.error(f"Failed to send 'P' to Arduino on {arduino.port}: {e}")

        # Make Ctrl+C work with PyQt event loop
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Use QTimer for polling instead of while True
        timer = QTimer()
        timer.timeout.connect(lambda: poll_hardware(app))
        timer.start(35)  # 35 ms interval

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