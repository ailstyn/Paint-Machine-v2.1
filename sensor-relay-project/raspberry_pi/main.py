import os
import serial
import time
import logging
import RPi.GPIO as GPIO
from gui.qt_gui import RelayControlApp
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import sys

# Configure logging
logging.basicConfig(
    filename="error_log.txt",  # Log file name
    level=logging.ERROR,       # Log level (ERROR and above)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# List of potential serial ports for the Arduinos
arduino_ports = [
    '/dev/ttyACM0',  # Adjust these ports as needed
    '/dev/ttyACM1',
    '/dev/ttyACM2',
    '/dev/ttyACM3'
]

# Create a list of active serial connections
arduinos = []
for port in arduino_ports:
    try:
        arduino = serial.Serial(port, 9600, timeout=1)
        arduinos.append(arduino)
        print(f"Connected to Arduino on {port}")
    except serial.SerialException:
        print(f"Port {port} not available. Skipping.")

if not arduinos:
    print("No Arduinos connected. Exiting program.")
    exit(1)  # Exit if no Arduinos are connected

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
TARE_SCALE = b'\x09'  # New byte for tare command
RELAY_DEACTIVATED = b'\xFA'
TARGET_WEIGHT = b'\x08'
VERBOSE_DEBUG = b'\xFE'
BEGIN_FILL = b'\x10'  # Choose an unused byte value for BEGIN_FILL

# GPIO pin assignments for buttons
UP_BUTTON_PIN = 5
DOWN_BUTTON_PIN = 6
SELECT_BUTTON_PIN = 16
E_STOP_PIN = 23
BUZZER_PIN = 26  # Add this near your other pin definitions

# Add a global flag for E-Stop
E_STOP = False

def load_scale_calibrations():
    # Load scale calibration values from the config file
    global scale_calibrations
    print("Loading scale calibration values...")

    # Get the full path to config.txt in the same directory as main.py
    config_path = os.path.join(os.path.dirname(__file__), config_file)

    try:
        with open(config_path, "r") as file:
            lines = file.readlines()
            scale_calibrations = [float(line.strip()) for line in lines]
        print(f"Loaded scale calibration values: {scale_calibrations}")
    except FileNotFoundError:
        logging.error(f"{config_path} not found. Using default calibration values.")
        scale_calibrations = [1.0, 1.0, 1.0, 1.0]  # Default calibration values
    except ValueError as e:
        logging.error(f"Error reading {config_path}: {e}")
        scale_calibrations = [1.0, 1.0, 1.0, 1.0]  # Default calibration values


def write_scale_calibrations():
    # Write scale calibration values to the config file
    try:
        with open(config_file, "w") as file:
            for value in scale_calibrations:
                file.write(f"{value}\n")
    except Exception as e:
        logging.error(f"Error writing to {config_file}: {e}")

def calibrate_scale(arduino_id, data_queue):
    # Initiate the scale recalibration process for the specified Arduino.

    if arduino_id < 0 or arduino_id >= len(arduinos):
        logging.error(f"Invalid Arduino ID: {arduino_id}")
        return

    arduino = arduinos[arduino_id]

    try:
        # Send the RESET_CALIBRATION message to the selected Arduino
        arduino.write(b'\x05')  # Example: Use b'\x05' for RESET_CALIBRATION
        print(f"Sent RESET_CALIBRATION to Arduino {arduino_id}")

        # Update the GUI to display "CLEAR SCALE"
        data_queue.put((arduino_id, {"current_weight": "CLEAR SCALE", "time_remaining": ""}))

        while True:
            if arduino.in_waiting > 0:
                # Read the message type (1 byte)
                message_type = arduino.read(1)

                # Handle "current weight" messages
                if message_type == CURRENT_WEIGHT:
                    current_weight = arduino.readline().decode('utf-8').strip()
                    data_queue.put((arduino_id, {"current_weight": current_weight, "time_remaining": ""}))

                # Handle recalibration steps
                elif message_type == b'\x06':  # Example: Use b'\x06' for "place calibration weight"
                    data_queue.put((arduino_id, {"current_weight": "PLACE WEIGHT ON SCALE", "time_remaining": ""}))
                    print("Arduino requested to place calibration weight.")

                elif message_type == b'\x07':  # Example: Use b'\x07' for "recalibration complete"
                    data_queue.put((arduino_id, {"current_weight": "CALIBRATION COMPLETE", "time_remaining": ""}))
                    print("Recalibration complete. Displaying message for 3 seconds...")
                    time.sleep(3)  # Wait for 3 seconds
                    break

            time.sleep(0.1)  # Small delay to avoid overwhelming the CPU

    except serial.SerialException as e:
        logging.error(f"Error communicating with Arduino {arduino_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during calibration: {e}")


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
    # Set up GPIO mode
    print('setting up GPIO')
    GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
    print('set mode BCM')
    GPIO.setup(UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Up button with pull-up resistor
    print('up button pin set')
    GPIO.setup(DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Down button with pull-up resistor
    print('down button pin set')
    GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Select button with pull-up resistor
    print('select button pin set')
    GPIO.setup(E_STOP_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # E-Stop button with pull-up resistor
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    GPIO.output(BUZZER_PIN, GPIO.LOW)


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
    if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:
        if app.selected_index > 0:
            ping_buzzer()
            app.update_selection_dot(app.selected_index - 1)
        else:
            ping_buzzer_invalid()
        time.sleep(0.2)
    if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:
        if app.selected_index < len(app.dot_widgets) - 1:
            ping_buzzer()
            app.update_selection_dot(app.selected_index + 1)
        else:
            ping_buzzer_invalid()
        time.sleep(0.2)
    if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
        ping_buzzer()
        # Wait for button release before executing the select action
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.01)
        app.handle_select()
        # Optional: small debounce after action
        time.sleep(0.1)

def startup(app):
    # Display the "CLEAR SCALES" message
    app.display_message("CLEAR SCALES", "PRESS SELECT WHEN READY")

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
    app.display_message("SCALES RESET", "")
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
            interval = 0.25  # Start at 4 times per second
            while GPIO.input(up_button_pin) == GPIO.LOW:
                elapsed = time.time() - start_time
                # Acceleration logic: decrease interval as button is held
                if elapsed >= 6:
                    interval = 1 / 32  # 32 times per second
                elif elapsed >= 4:
                    interval = 1 / 16  # 16 times per second
                elif elapsed >= 2:
                    interval = 1 / 8   # 8 times per second
                else:
                    interval = 0.25    # 4 times per second

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
            interval = 0.25  # Start at 4 times per second
            while GPIO.input(down_button_pin) == GPIO.LOW:
                elapsed = time.time() - start_time
                if elapsed >= 6:
                    interval = 1 / 32
                elif elapsed >= 4:
                    interval = 1 / 16
                elif elapsed >= 2:
                    interval = 1 / 8
                else:
                    interval = 0.25

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
    print("Opening target weight dialog...")
    dialog = app.create_value_input_dialog(
        title="SET TARGET WEIGHT",
        initial_value=target_weight,
        unit="g"
    )
    target_weight = adjust_value_with_acceleration(
        initial_value=target_weight,
        dialog=dialog,
        up_button_pin=UP_BUTTON_PIN,
        down_button_pin=DOWN_BUTTON_PIN,
        unit_increment=1,
        min_value=0
    )
    print("Closed target weight dialog.")

# Usage in set_time_limit:
def set_time_limit(app):
    global time_limit
    print("Opening time limit dialog...")
    dialog = app.create_value_input_dialog(
        title="SET TIME LIMIT",
        initial_value=time_limit,
        unit="ms"
    )
    time_limit = adjust_value_with_acceleration(
        initial_value=time_limit,
        dialog=dialog,
        up_button_pin=UP_BUTTON_PIN,
        down_button_pin=DOWN_BUTTON_PIN,
        unit_increment=100,
        min_value=0
    )
    print("Closed time limit dialog.")

def poll_hardware(app):
    global E_STOP
    try:
        arduino = arduinos[0]  # Only use the first Arduino for now

        # Check E-Stop status
        if GPIO.input(E_STOP_PIN) == GPIO.LOW:
            if not E_STOP:
                E_STOP = True
                app.show_overlay("E-STOP ACTIVATED", "")
            # If E-Stop is active, respond to any message except CURRENT_WEIGHT
            while arduino.in_waiting > 0:
                message_type = arduino.read(1)
                if message_type == CURRENT_WEIGHT:
                    pass
                else:
                    arduino.write(RELAY_DEACTIVATED)
        else:
            handle_button_presses(app)
            while arduino.in_waiting > 0:
                message_type = arduino.read(1)
                if message_type == REQUEST_TARGET_WEIGHT:
                    print("Arduino requested target weight.")
                    arduino.write(TARGET_WEIGHT)
                    arduino.write(f"{target_weight}\n".encode('utf-8'))
                    print(f"Sent target weight to Arduino: {target_weight}")
                elif message_type == REQUEST_CALIBRATION:
                    print("Arduino requested calibration value.")
                    arduino.write(REQUEST_CALIBRATION)
                    arduino.write(f"{scale_calibrations[0]}\n".encode('utf-8'))
                    print(f"Sent calibration value to Arduino: {scale_calibrations[0]}")
                elif message_type == REQUEST_TIME_LIMIT:
                    print("Arduino requested time limit.")
                    arduino.write(REQUEST_TIME_LIMIT)
                    arduino.write(f"{time_limit}\n".encode('utf-8'))
                    print(f"Sent time limit to Arduino: {time_limit}")
                elif message_type == CURRENT_WEIGHT:
                    current_weight = arduino.readline().decode('utf-8').strip()
                    app.current_weight = float(current_weight)
                    app.target_weight = float(target_weight)
                    app.refresh_ui()
                elif message_type == BEGIN_FILL:
                    print("Received BEGIN FILL from Arduino.")
                    app.set_fill_mode(target_weight)  # You need to implement set_fill_mode in your GUI
                elif message_type == VERBOSE_DEBUG:
                    debug_line = arduino.readline().decode('utf-8', errors='replace').strip()
                    print(f"Arduino (debug): {debug_line}")
                else:
                    # Read and print any unexpected lines from Arduino
                    possible_line = arduino.readline().decode('utf-8', errors='replace').strip()
                    print(f"Arduino (unhandled): {possible_line}")
                    logging.warning(f"Unhandled message type: {message_type} | Line: {possible_line}")
        # At the end, update the GUI:
        app.refresh_ui()  # Or just update the widgets here
        
    except Exception as e:
        logging.error(f"Error in poll_hardware: {e}")

def main():
    try:
        load_scale_calibrations()
        setup_gpio()
        app_qt = QApplication(sys.argv)
        app = RelayControlApp(
            set_target_weight_callback=set_target_weight,
            set_time_limit_callback=set_time_limit
        )
        # app.show()
        print('app initialized, contacting arduinos')

        # Clear serial buffers before starting communication
        for arduino in arduinos:
            arduino.reset_input_buffer()
            arduino.reset_output_buffer()

        # Send 'P' (PI READY) to all connected Arduinos after GUI is ready
        for arduino in arduinos:
            try:
                arduino.write(b'P')
                print(f"Sent 'P' (PI READY) to Arduino on {arduino.port}")
            except Exception as e:
                logging.error(f"Failed to send 'P' to Arduino on {arduino.port}: {e}")

        # Start polling loop using QTimer instead of root.after
        poll_timer = QTimer()
        poll_timer.timeout.connect(lambda: poll_hardware(app))
        poll_timer.start(100)

        sys.exit(app_qt.exec())
    except KeyboardInterrupt:
        print("Program interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        print("Shutting down...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()