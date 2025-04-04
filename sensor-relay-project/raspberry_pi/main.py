import serial
import time
import logging
from threading import Thread
from gui.machine_gui import RelayControlApp  # Updated import
from tkinter import Tk

# Configure logging
logging.basicConfig(
    filename="error_log.txt",  # Log file name
    level=logging.ERROR,       # Log level (ERROR and above)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# List of serial ports for the Arduinos
arduino_ports = [
    '/dev/ttyUSB0',  # Adjust these ports as needed
    '/dev/ttyUSB1',
    '/dev/ttyUSB2',
    '/dev/ttyUSB3'
]

# Create a list of serial connections
try:
    arduinos = [serial.Serial(port, 9600, timeout=1) for port in arduino_ports]
except serial.SerialException as e:
    logging.error(f"Failed to initialize serial connections: {e}")
    raise

# Shared target weight variable
target_weight = 500.0  # Example target weight in grams

# File to store scale calibration values
config_file = "config.txt"

def read_config():
    """Read scale calibration values from the config file."""
    try:
        with open(config_file, "r") as file:
            lines = file.readlines()
            return [float(line.strip()) for line in lines]
    except FileNotFoundError:
        logging.error(f"{config_file} not found. Using default calibration values.")
        return [1.0, 1.0, 1.0, 1.0]  # Default calibration values
    except ValueError as e:
        logging.error(f"Error reading {config_file}: {e}")
        return [1.0, 1.0, 1.0, 1.0]  # Default calibration values

def write_config(calibration_values):
    """Write scale calibration values to the config file."""
    try:
        with open(config_file, "w") as file:
            for value in calibration_values:
                file.write(f"{value}\n")
    except Exception as e:
        logging.error(f"Error writing to {config_file}: {e}")

def arduino_communication():
    """Handle communication with Arduinos."""
    # Load scale calibration values
    scale_calibrations = read_config()
    print(f"Loaded scale calibration values: {scale_calibrations}")

    try:
        while True:
            for i, arduino in enumerate(arduinos):
                try:
                    if arduino.in_waiting > 0:
                        message = arduino.readline().decode('utf-8').strip()
                        if message == "REQUEST_TARGET_WEIGHT":
                            print(f"Arduino on {arduino.port} requested target weight.")
                            arduino.write(f"tw_{target_weight}\n".encode('utf-8'))
                        elif message.startswith("SET_CALIBRATION"):
                            # Example: "SET_CALIBRATION 1.23"
                            _, value = message.split()
                            scale_calibrations[i] = float(value)
                            write_config(scale_calibrations)
                            print(f"Updated calibration for Arduino on {arduino.port}: {value}")
                        else:
                            print(f"Received from Arduino on {arduino.port}: {message}")
                except serial.SerialException as e:
                    logging.error(f"Error communicating with Arduino on {arduino.port}: {e}")
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

def run_gui():
    """Run the GUI."""
    root = Tk()
    app = RelayControlApp(root)
    root.mainloop()

def main():
    # Run the GUI in a separate thread
    gui_thread = Thread(target=run_gui)
    gui_thread.daemon = True  # Ensure the thread exits when the main program exits
    gui_thread.start()

    # Start Arduino communication
    arduino_communication()

if __name__ == "__main__":
    main()