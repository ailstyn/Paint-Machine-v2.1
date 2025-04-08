import serial
import time

def main():
    # Replace '/dev/ttyUSB0' with the correct port for your Arduino
    arduino_port = '/dev/ttyACM0'
    baud_rate = 9600

    try:
        # Initialize the serial connection
        arduino = serial.Serial(arduino_port, baud_rate, timeout=1)
        arduino.reset_input_buffer()  # Clear the input buffer
        print(f"Connected to Arduino on {arduino_port}")
    except serial.SerialException as e:
        print(f"Error: Could not connect to Arduino on {arduino_port}. {e}")
        return

    try:
        while True:
            input("Press Enter to start reading from serial...")  # Wait for user input
            print("Reading from serial. Press Ctrl+C to stop.")
            
            # Continuously read and print data from the serial port
            while True:
                if arduino.in_waiting > 0:
                    response = arduino.readline().decode('utf-8').strip()
                    print(f"Received: {response}")

    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        arduino.close()

if __name__ == "__main__":
    main()