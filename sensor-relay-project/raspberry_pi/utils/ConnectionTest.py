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
            print("Reading from serial for 20 iterations. Press Ctrl+C to stop.")

            response_values = []  # List to store numeric response values
            iteration_times = []  # List to store the time taken for each iteration

            for i in range(20):  # Run for 20 iterations
                start_time = time.time()  # Record the start time

                if arduino.in_waiting > 0:
                    response = arduino.readline().decode('utf-8').strip()
                    print(f"Iteration {i + 1}: Received: {response}")

                    # Extract numeric value from the response
                    if response.startswith("Weight:"):
                        try:
                            value = float(response.split(":")[1].strip())
                            response_values.append(value)
                        except ValueError:
                            print(f"Warning: Could not parse numeric value from response: {response}")

                end_time = time.time()  # Record the end time
                iteration_time = end_time - start_time  # Calculate the time taken
                iteration_times.append(iteration_time)  # Store the iteration time

            # Calculate the range of response values
            if response_values:
                max_value = max(response_values)
                min_value = min(response_values)
                value_range = max_value - min_value

                print(f"\nHighest value: {max_value}")
                print(f"Lowest value: {min_value}")
                print(f"Range of values: {value_range}")
            else:
                print("\nNo valid numeric responses received.")

            # Calculate the average response time
            if iteration_times:
                average_time = sum(iteration_times) / len(iteration_times)
                print(f"Average response time: {average_time:.4f} seconds")
            else:
                print("No valid response times recorded.")

            break  # Exit after 20 iterations

    except KeyboardInterrupt:
        print("\nExiting program.")
    finally:
        arduino.close()

if __name__ == "__main__":
    main()