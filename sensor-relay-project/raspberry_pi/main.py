import serial
import time

# List of serial ports for the Arduinos
arduino_ports = [
    '/dev/ttyUSB0',  # Adjust these ports as needed
    '/dev/ttyUSB1',
    '/dev/ttyUSB2',
    '/dev/ttyUSB3'
]

# Create a list of serial connections
arduinos = [serial.Serial(port, 9600, timeout=1) for port in arduino_ports]

# Shared target weight variable
target_weight = 500.0  # Example target weight in grams

def main():
    try:
        while True:
            for arduino in arduinos:
                if arduino.in_waiting > 0:
                    message = arduino.readline().decode('utf-8').strip()
                    if message == "REQUEST_TARGET_WEIGHT":
                        print(f"Arduino on {arduino.port} requested target weight.")
                        arduino.write(f"{target_weight}\n".encode('utf-8'))
                    else:
                        print(f"Received from Arduino on {arduino.port}: {message}")

            time.sleep(0.1)  # Small delay to avoid overwhelming the CPU

    except KeyboardInterrupt:
        print("Exiting program.")
    finally:
        for arduino in arduinos:
            arduino.close()

if __name__ == "__main__":
    main()