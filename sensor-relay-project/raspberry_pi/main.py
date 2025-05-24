import os
import serial
import time
import logging
from tkinter import Tk, Label, StringVar
import RPi.GPIO as GPIO
from gui import machine_gui

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

# GPIO pin assignments for buttons
UP_BUTTON_PIN = 5
DOWN_BUTTON_PIN = 6
SELECT_BUTTON_PIN = 16
E_STOP_PIN = 23

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


def handle_button_presses(app):
    if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:  # UP button pressed
        print("Up button pressed")
        app.move_selection("up")  # Move the selection up
        time.sleep(0.2)  # Debounce delay

    if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:  # DOWN button pressed
        print("Down button pressed")
        app.move_selection("down")  # Move the selection down
        time.sleep(0.2)  # Debounce delay

    if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:  # SELECT button pressed
        print("Select button pressed")
        set_target_weight(app)  # Call the set_target_weight function

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

def set_target_weight(app):
    """
    Allow the user to manually change the target weight using the UP, DOWN, and SELECT buttons.
    If E_STOP is active, send RELAY_DEACTIVATED and exit.
    """
    global target_weight

    if E_STOP:
        print("E-Stop is active. Cannot set target weight.")
        for i, arduino in enumerate(arduinos):
            try:
                arduino.write(b"RELAY DEACTIVATED\n")  # Send the relay deactivated message
                print(f"Sent RELAY DEACTIVATED to Arduino {i} on port {arduino.port}")
            except serial.SerialException as e:
                logging.error(f"Error sending RELAY DEACTIVATED to Arduino {i} on port {arduino.port}: {e}")
        return

    print(f"Current target weight: {target_weight}g")
    app.display_message("SET TARGET WEIGHT", f"{target_weight}g")

    while True:
        # Check for button presses
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:  # UP button pressed
            target_weight += 10  # Increase target weight by 10g
            print(f"Target weight increased to: {target_weight}g")
            app.display_message("SET TARGET WEIGHT", f"{target_weight}g")
            time.sleep(0.2)  # Debounce delay

        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:  # DOWN button pressed
            target_weight = max(0, target_weight - 10)  # Decrease target weight by 10g, minimum 0g
            print(f"Target weight decreased to: {target_weight}g")
            app.display_message("SET TARGET WEIGHT", f"{target_weight}g")
            time.sleep(0.2)  # Debounce delay

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:  # SELECT button pressed
            print(f"Target weight set to: {target_weight}g")
            app.display_message("TARGET WEIGHT SET", f"{target_weight}g")
            time.sleep(2)  # Display confirmation message for 2 seconds
            app.reload_main_screen()  # Return to the main screen
            break

def set_time_limit(app):
    """
    Allow the user to manually change the time limit using the UP, DOWN, and SELECT buttons.
    If E_STOP is active, send RELAY_DEACTIVATED and exit.
    """
    global time_limit

    if E_STOP:
        print("E-Stop is active. Cannot set time limit.")
        logging.error('E-Stop is active. Cannot set time limit.')
        return

    while True:
        # Check for button presses
        if GPIO.input(UP_BUTTON_PIN) == GPIO.LOW:  # UP button pressed
            time_limit += 100  # Increase time limit by 100ms
            print(f"Time limit increased to: {time_limit}ms")
            app.display_message("SET TIME LIMIT", f"{time_limit}ms")
            time.sleep(0.2)  # Debounce delay

        if GPIO.input(DOWN_BUTTON_PIN) == GPIO.LOW:  # DOWN button pressed
            time_limit = max(0, time_limit - 100)  # Decrease time limit by 100ms, minimum 0ms
            print(f"Time limit decreased to: {time_limit}ms")
            app.display_message("SET TIME LIMIT", f"{time_limit}ms")
            time.sleep(0.2)  # Debounce delay

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:  # SELECT button pressed
            print(f"Time limit set to: {time_limit}ms")
            app.display_message("TIME LIMIT SET", f"{time_limit}ms")
            time.sleep(2)  # Display confirmation message for 2 seconds
            app.reload_main_screen()  # Return to the main screen
            break

def poll_hardware(app, root):
    global E_STOP
    try:
        arduino = arduinos[0]  # Only use the first Arduino for now

        # Check E-Stop status
        if GPIO.input(E_STOP_PIN) == GPIO.LOW:
            if not E_STOP:
                E_STOP = True
                app.display_e_stop()
            # If E-Stop is active, respond to any message except CURRENT_WEIGHT
            while arduino.in_waiting > 0:
                message_type = arduino.read(1)
                if message_type == CURRENT_WEIGHT:
                    pass
                else:
                    arduino.write(b"RELAY DEACTIVATED\n")
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
                    app.update_data(0, {
                        "current_weight": current_weight,
                        "target_weight": target_weight,
                        "time_remaining": ""
                    })
                else:
                    logging.warning(f"Unhandled message type: {message_type}")
    except Exception as e:
        logging.error(f"Error in poll_hardware: {e}")

    # Schedule next poll
    root.after(100, poll_hardware, app, root)

def main():
    try:
        load_scale_calibrations()
        setup_gpio()
        root = Tk()
        app = machine_gui.RelayControlApp(root)
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

        poll_hardware(app, root)  # Start polling loop
        root.mainloop()
    except KeyboardInterrupt:
        print("Program interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
    finally:
        print("Shutting down...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()