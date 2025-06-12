import serial
import time
import statistics

# Adjust the port as needed
port = '/dev/ttyACM0'  # Change if your Arduino is on a different port
baudrate = 9600

try:
    arduino = serial.Serial(port, baudrate, timeout=1)
    print(f"Connected to Arduino on {port}")
except serial.SerialException:
    print(f"Could not open port {port}.")
    exit(1)

CURRENT_WEIGHT = b'\x04'

count = 0
timeout = 10  # seconds
overall_start = time.time()  # Start overall timer
weights = []

print("Starting serial test for 25 weight readings...")
start_time = time.time()  # Start timer for reading loop
while count < 25 and (time.time() - start_time) < timeout:
    if arduino.in_waiting > 0:
        message_type = arduino.read(1)
        if message_type == CURRENT_WEIGHT:
            current_weight = arduino.readline().decode('utf-8').strip()
            try:
                weight_val = float(current_weight)
                weights.append(weight_val)
            except ValueError:
                print(f"Non-numeric weight received: {current_weight}")
                continue
            print(f"Weight reading {count+1}: {current_weight}")
            count += 1
            start_time = time.time()  # reset timeout after successful read
    time.sleep(0.1)

end_time = time.time()
arduino.close()
print("Serial test complete.")
print(f"Time elapsed for 25 readings: {end_time - overall_start:.2f} seconds")

if weights:
    print(f"Max weight: {max(weights)}")
    print(f"Min weight: {min(weights)}")
    print(f"Mean weight: {statistics.mean(weights):.2f}")
    print(f"Median weight: {statistics.median(weights):.2f}")
else:
    print("No valid weight readings received.")