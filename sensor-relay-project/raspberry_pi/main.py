import serial
import time
import logging
from threading import Thread
from queue import Queue
from gui.machine_gui import RelayControlApp
from tkinter import Tk

# Configure logging
logging.basicConfig(
    filename="error_log.txt",  # Log file name
    level=logging.ERROR,       # Log level (ERROR and above)
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# List of serial ports for the Arduinos
arduino_ports = [
    '/dev/ttyACM0',  # Adjust these ports as needed
    '/dev/ttyACM1',
    '/dev/ttyACM2',
    '/dev/ttyACM3'
]

# Create a list of serial connections
try:
    arduinos = [serial.Serial(port, 9600, timeout=1) for port in arduino_ports]
except serial.SerialException as e:
    logging.error(f"Failed to initialize serial connections: {e}")
    raise

# Shared variables
target_weight = 500.0  # Example target weight in grams
config_file = "config.txt"  # File to store scale calibration values
scale_calibrations = []  # List to hold calibration values


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
                    # Check if the Arduino is connected and has data to read
                    if arduino.in_waiting > 0:
                        message = arduino.readline().decode('utf-8').strip()
                        
                        if message == "REQUEST_TARGET_WEIGHT":
                            print(f"Arduino on {arduino.port} requested target weight.")
                            arduino.write(f"tw_{target_weight}\n".encode('utf-8'))
                        
                        elif message == "REQUEST_CALIBRATION":
                            print(f"Arduino on {arduino.port} requested calibration value.")
                            arduino.write(f"cal_{scale_calibrations[i]}\n".encode('utf-8'))
                        
                        elif message == "REQUEST_TIME_LIMIT":
                            print(f"Arduino on {arduino.port} requested time limit.")
                            time_limit = 3000  # Example: Set the time limit to 3000 ms (3 seconds)
                            arduino.write(f"tl_{time_limit}\n".encode('utf-8'))

                    # Continuously send updates for current weight and time remaining
                    # If the Arduino is connected, send the data
                    data = {
                        "current_weight": f"{scale_calibrations[i]}g",  # Example: Replace with actual weight reading
                        "time_remaining": "10s",  # Example: Replace with actual time remaining
                    }
                    data_queue.put((i, data))

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

    # Args:
    #    arduino_id: The ID of the Arduino to recalibrate (0-3).
    
    if arduino_id < 0 or arduino_id >= len(arduinos):
        logging.error(f"Invalid Arduino ID: {arduino_id}")
        return

    arduino = arduinos[arduino_id]

    try:
        # Send the RESET_CALIBRATION message to the selected Arduino
        arduino.write("RESET_CALIBRATION\n".encode('utf-8'))
        print(f"Sent RESET_CALIBRATION to Arduino {arduino_id}")

        # Update the GUI to display "CLEAR SCALE"
        data_queue.put((arduino_id, {"current_weight": "CLEAR SCALE", "time_remaining": ""}))

        while True:
            if arduino.in_waiting > 0:
                message = arduino.readline().decode('utf-8').strip()

                # Display the current weight being sent from the Arduino
                if message.startswith("Current Weight:"):
                    current_weight = message.split(":")[1].strip()
                    data_queue.put((arduino_id, {"current_weight": current_weight, "time_remaining": ""}))

                # Handle Arduino messages for recalibration steps
                elif message == "Scale reset and tared. Place calibration weight.":
                    data_queue.put((arduino_id, {"current_weight": "PLACE WEIGHT ON SCALE", "time_remaining": ""}))
                    print("Arduino requested to place calibration weight.")

                elif message == "Recalibration complete":
                    data_queue.put((arduino_id, {"current_weight": "CALIBRATION COMPLETE", "time_remaining": ""}))
                    print("Recalibration complete. Displaying message for 3 seconds...")
                    time.sleep(3)  # Wait for 3 seconds
                    break

            time.sleep(0.1)  # Small delay to avoid overwhelming the CPU

    except serial.SerialException as e:
        logging.error(f"Error communicating with Arduino {arduino_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error during calibration: {e}")


def run_gui(data_queue):
    # Run the GUI
    root = Tk()
    app = RelayControlApp(root)

    def update_gui():
        # Update the GUI with data from the queue
        while not data_queue.empty():
            arduino_id, new_data = data_queue.get()
            app.update_data(arduino_id, new_data)
        root.after(100, update_gui)  # Schedule the next update

    update_gui()  # Start the update loop
    root.mainloop()


def main(data_queue):
    # Load scale calibration values at startup
    load_scale_calibrations()

    # Create a thread-safe queue for communication between threads
    data_queue = Queue()

    # Run the GUI in a separate thread
    gui_thread = Thread(target=run_gui, args=(data_queue,))
    gui_thread.daemon = True  # Ensure the thread exits when the main program exits
    gui_thread.start()

    # Start Arduino communication
    arduino_communication(data_queue)


if __name__ == "__main__":
    data_queue = Queue()
    main(data_queue)