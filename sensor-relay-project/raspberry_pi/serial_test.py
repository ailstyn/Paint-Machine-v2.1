import serial
import time

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
start_time = time.time()

print("Starting serial test for 25 weight readings...")
while count < 25 and (time.time() - start_time) < timeout:
    if arduino.in_waiting > 0:
        message_type = arduino.read(1)
        if message_type == CURRENT_WEIGHT:
            current_weight = arduino.readline().decode('utf-8').strip()
            print(f"Weight reading {count+1}: {current_weight}")
            count += 1
            start_time = time.time()  # reset timeout after successful read
    time.sleep(0.1)

arduino.close()
print("Serial test complete.")