def open_serial_port(port, baudrate=9600):
    import serial
    try:
        ser = serial.Serial(port, baudrate)
        return ser
    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
        return None

def read_from_serial(ser):
    if ser and ser.in_waiting > 0:
        return ser.readline().decode('utf-8').strip()
    return None

def send_to_serial(ser, data):
    if ser:
        ser.write(data.encode('utf-8'))