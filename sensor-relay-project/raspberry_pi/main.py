import os
import serial
import time
import logging
from threading import Thread
from queue import Queue
from gui.machine_gui import RelayControlApp
from tkinter import Tk, Label
import RPi.GPIO as GPIO

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

# GPIO pin assignments for buttons
UP_BUTTON_PIN = 17      # GPIO pin for the "up" button
DOWN_BUTTON_PIN = 27    # GPIO pin for the "down" button
SELECT_BUTTON_PIN = 22  # GPIO pin for the "select" button

# Add a global flag for E-Stop
E_STOP = False

# GPIO pin for the E-Stop button
E_STOP_PIN = 23  # Use an unused GPIO pin


def load_scale_calibrations():
    # Load scale calibration values from the config file
    global scale_calibrations
    try:
        with open(config_file, "r") as file:
            lines = file.readlines()
            scale_calibrations = [float(line.strip()) for line in lines]
        print(f"Loaded scale calibration values: {scale_calibrations}")
    except FileNotFoundError:
        logging.error(f"{config_file} not found. Using default calibration values.")
        scale_calibrations = [1.0, 1.0, 1.0, 1.0]  # Default calibration values
    except ValueError as e:
        logging.error(f"Error reading {config_file}: {e}")
        scale_calibrations = [1.0, 1.0, 1.0, 1.0]  # Default calibration values


def write_scale_calibrations():
    # Write scale calibration values to the config file
    try:
        with open(config_file, "w") as file:
            for value in scale_calibrations:
                file.write(f"{value}\n")
    except Exception as e:
        logging.error(f"Error writing to {config_file}: {e}")


def arduino_communication(data_queue):
    # Handle communication with Arduinos
    try:
        while True:
            for i, arduino in enumerate(arduinos):
                try:
                    # Check if the Arduino has data to read
                    while arduino.in_waiting > 0:
                        # Read the message type (1 byte)
                        message_type = arduino.read(1)

                        # Handle "request target weight" messages
                        if message_type == REQUEST_TARGET_WEIGHT:
                            if E_STOP:
                                print(f"Arduino on {arduino.port} requested target weight, but E-Stop is active.")
                                arduino.write(b"RELAY DEACTIVATED\n")  # Send relay deactivated message
                            else:
                                print(f"Arduino on {arduino.port} requested target weight.")
                                arduino.write(REQUEST_TARGET_WEIGHT)  # Send the REQUEST_TARGET_WEIGHT message type
                                arduino.write(f"{target_weight}\n".encode('utf-8'))  # Send the target weight as a string

                        # Handle "request calibration" messages
                        elif message_type == REQUEST_CALIBRATION:
                            print(f"Arduino on {arduino.port} requested calibration value.")
                            arduino.write(f"{scale_calibrations[i]}\n".encode('utf-8'))

                        # Handle "request time limit" messages
                        elif message_type == REQUEST_TIME_LIMIT:
                            print(f"Arduino on {arduino.port} requested time limit.")
                            arduino.write(f"{time_limit}\n".encode('utf-8'))

                        # Handle "current weight" messages
                        elif message_type == CURRENT_WEIGHT:
                            current_weight = arduino.readline().decode('utf-8').strip()
                            data_queue.put((i, {"current_weight": current_weight, "time_remaining": ""}))

                        else:
                            # Log unexpected or unhandled messages
                            logging.warning(f"Unhandled message type from Arduino on {arduino.port}: {message_type}")

                except serial.SerialException:
                    # If the Arduino is disconnected, send "SCALE DISCONNECTED"
                    data_queue.put((i, {"current_weight": "SCALE DISCONNECTED",
                                        "time_remaining": "SCALE DISCONNECTED"}))
                except Exception as e:
                    logging.error(f"Unexpected error with Arduino on {arduino.port}: {e}")

            time.sleep(0.1)  # Small delay to avoid overwhelming the CPU

    except KeyboardInterrupt:
        print("Exiting program.")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
    finally:
        for arduino in arduinos:
            try:
                arduino.close()
            except serial.SerialException as e:
                logging.error(f"Error closing connection to Arduino on {arduino.port}: {e}")


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
    """
    Send a command to the specified Arduino to tare the scale.

    Args:
        arduino_id: The ID of the Arduino to send the tare command to.
    """
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
    GPIO.setmode(GPIO.BCM)  # Use BCM pin numbering
    GPIO.setup(UP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Up button with pull-up resistor
    GPIO.setup(DOWN_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Down button with pull-up resistor
    GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Select button with pull-up resistor
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


def run_gui(data_queue):
    # Run the GUI
    root = Tk()
    app = RelayControlApp(root)

    def update_gui():
        # Update the GUI with data from the queue
        if E_STOP:
            app.display_e_stop()  # Show the E-Stop message
        else:
            while not data_queue.empty():
                arduino_id, new_data = data_queue.get()
                app.update_data(arduino_id, new_data)
        root.after(100, update_gui)  # Schedule the next update

    update_gui()  # Start the update loop
    root.mainloop()


def display_message(self, main_message, sub_message):
    """
    Display a temporary message on the GUI.

    Args:
        main_message: The main message to display (e.g., "CLEAR SCALES").
        sub_message: The sub-message to display (e.g., "PRESS SELECT WHEN READY").
    """
    # Clear the GUI
    for widget in self.master.winfo_children():
        widget.destroy()

    # Display the main message
    Label(self.master, text=main_message, font=('Cascadia Code SemiBold', 48), bg="black", fg="red").pack(pady=20)

    # Display the sub-message
    Label(self.master, text=sub_message, font=('Cascadia Code SemiBold', 24), bg="black", fg="white").pack(pady=10)

def startup(app):
    # Display the "CLEAR SCALES" message
    app.display_message("CLEAR SCALES", "PRESS SELECT WHEN READY")

    # Wait for the select button to be pressed
    while GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:  # Wait until the button is pressed (LOW)
        time.sleep(0.1)

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
        for i, arduino in enumerate(arduinos):
            try:
                arduino.write(b"RELAY DEACTIVATED\n")  # Send the relay deactivated message
                print(f"Sent RELAY DEACTIVATED to Arduino {i} on port {arduino.port}")
            except serial.SerialException as e:
                logging.error(f"Error sending RELAY DEACTIVATED to Arduino {i} on port {arduino.port}: {e}")
        return

    print(f"Current time limit: {time_limit}ms")
    app.display_message("SET TIME LIMIT", f"{time_limit}ms")

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

def monitor_e_stop():
    """
    Monitor the E-Stop button and set the E_STOP flag to True when pressed.
    Notify all connected Arduinos about the E-Stop activation.
    """
    global E_STOP

    if GPIO.input(E_STOP_PIN) == GPIO.LOW:  # E-Stop button pressed
        if not E_STOP:  # Only send the message once when E-Stop is activated
            print("E-Stop activated!")
            E_STOP = True

            # Notify all connected Arduinos
            for i, arduino in enumerate(arduinos):
                try:
                    arduino.write(b"RELAY DEACTIVATED\n")  # Send the relay deactivated message
                    print(f"Sent RELAY DEACTIVATED to Arduino {i} on port {arduino.port}")
                except serial.SerialException as e:
                    logging.error(f"Error sending RELAY DEACTIVATED to Arduino {i} on port {arduino.port}: {e}")

def turn_usb_power_off():
    """
    Disable power to all USB ports.
    Requires root privileges and proper Raspberry Pi configuration.
    """
    try:
        with open("/sys/devices/platform/soc/3f980000.usb/buspower", "w") as usb_power_file:
            usb_power_file.write("0")  # Write '0' to disable USB power
        print("USB power disabled.")
    except FileNotFoundError:
        logging.error("USB power control file not found. Ensure the Raspberry Pi is configured correctly.")
    except PermissionError:
        logging.error("Permission denied. Run the program as root to control USB power.")
    except Exception as e:
        logging.error(f"Unexpected error while disabling USB power: {e}")

def main(data_queue, app):
    # Turn on USB power at startup
    #turn_usb_power_on()

    # Load scale calibration values at startup
    load_scale_calibrations()

    # Set up GPIO
    setup_gpio()

    # Create a thread-safe queue for communication between threads
    data_queue = Queue()

    # Run the GUI in a separate thread
    root = Tk()
    app = RelayControlApp(root)

    # Show the startup message
    startup(app)

    # Start the GUI update loop
    gui_thread = Thread(target=run_gui, args=(data_queue,))
    gui_thread.daemon = True  # Ensure the thread exits when the main program exits
    gui_thread.start()

    try:
        # Start Arduino communication
        while True:
            arduino_communication(data_queue)  # Handle other Arduino communication
            handle_button_presses(app)  # Check for button presses
            monitor_e_stop()  # Check the E-Stop button and notify Arduinos if needed
            time.sleep(0.1)  # Small delay to avoid high CPU usage
    except KeyboardInterrupt:
        print("Exiting program.")
    finally:
        # Turn off USB power at shutdown
        turn_usb_power_off()
        GPIO.cleanup()  # Clean up GPIO on exit


if __name__ == "__main__":
    data_queue = Queue()
    root = Tk()
    app = RelayControlApp(root)
    main(data_queue, app)