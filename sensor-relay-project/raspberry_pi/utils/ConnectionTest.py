import serial
import time

def main():
    # Replace '/dev/ttyUSB0' with the correct port for your Arduino
    arduino_port = '/dev/ttyUSB0'
    baud_rate = 9600

    try:
        # Initialize the serial connection
        arduino = serial.Serial(arduino_port, baud_rate, timeout=1)
        print(f"Connected to Arduino on {arduino_port}")
    except serial.SerialException as e:
        print(f"Error: Could not connect to Arduino on {arduino_port}. {e}")
        return

    try:
        while True:
            input("Press Enter to send signal...")  # Wait for user input
            arduino.write("CONNECTION_TEST\n".encode('utf-8'))  # Send the test message
            print("Signal sent. Waiting for response...")

            # Wait for the response from the Arduino
            start_time = time.time()
            while True:
                if arduino.in_waiting > 0:
                    response = arduino.readline().decode('utf-8').strip()
                    if response == "ARDUINO_ONLINE":
                        print("arduino is connected")
                        break
                # Timeout after 5 seconds if no response
                if time.time() - start_time > 5:
                    print("Error: No response from Arduino.")
                    break

    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        arduino.close()

if __name__ == "__main__":
    main()