import sys
import logging
import serial
import serial.tools.list_ports

# Protocol bytes
GET_ID = b'\xA0'
TARE_SCALE = b'\x09'
RESET_CALIBRATION = b'\x05'
CALIBRATION_CONTINUE = b'\x13'
CALIBRATION_STEP_DONE = b'\x12'
CALIBRATION_WEIGHT = b'\x14'

config_file = "config.txt"

def get_station_id(ser):
    ser.reset_input_buffer()
    ser.write(GET_ID)
    ser.flush()
    line = ser.readline().decode('utf-8', errors='replace').strip()
    try:
        return int(line)
    except ValueError:
        return None

def scan_arduinos_by_station_id(baudrate=115200, timeout=1):
    ports = list(serial.tools.list_ports.comports())
    arduinos = {}
    port_labels = {}
    for port in ports:
        try:
            ser = serial.Serial(port.device, baudrate, timeout=timeout)
            station_id = get_station_id(ser)
            if station_id is not None:
                arduinos[station_id] = ser
                port_labels[station_id] = f"station{station_id}: {port.device} ({port.description})"
            else:
                ser.close()
        except Exception as e:
            logging.error(f"Could not open {port.device}: {e}")
    return arduinos, port_labels

def read_station_config(config_file):
    """Read calibration and enabled flags for all stations from config.txt."""
    station_config = {}
    try:
        with open(config_file, "r") as file:
            for line in file:
                if line.startswith("station") and "=" in line:
                    key, value = line.strip().split("=", 1)
                    if "_calibration" in key:
                        station = key.split("_")[0]
                        station_config.setdefault(station, {})["calibration"] = float(value)
                    elif "_enabled" in key:
                        station = key.split("_")[0]
                        station_config.setdefault(station, {})["enabled"] = value.lower() == "true"
    except FileNotFoundError:
        pass
    return station_config

def write_station_calibration(config_file, station_id, calibration_value):
    """Update calibration value for a station in config.txt."""
    lines = []
    found = False
    key = f"station{station_id}_calibration"
    try:
        with open(config_file, "r") as file:
            for line in file:
                if line.startswith(key + "="):
                    lines.append(f"{key}={calibration_value}\n")
                    found = True
                else:
                    lines.append(line)
    except FileNotFoundError:
        pass
    if not found:
        lines.append(f"{key}={calibration_value}\n")
    with open(config_file, "w") as file:
        file.writelines(lines)

def calibrate_scale(station_id, arduino):
    try:
        print(f"[calibrate_scale] Starting calibration for station {station_id}")

        arduino.write(RESET_CALIBRATION)
        arduino.flush()
        print("[calibrate_scale] Sent RESET_CALIBRATION to Arduino")

        print("Step 1: Remove all weight from the scale, then press ENTER to continue.")
        input()
        clear_serial_buffer(arduino)
        arduino.write(CALIBRATION_CONTINUE)
        arduino.flush()
        print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino")

        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE from Arduino")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE from Arduino")
                    break

        calib_weight = 100
        print(f"Step 2: Place a calibration weight on the scale (default: {calib_weight}g).")
        user_input = input("Enter calibration weight in grams (or press ENTER to use default): ")
        if user_input.strip():
            try:
                calib_weight = float(user_input.strip())
            except ValueError:
                print("Invalid input, using default value.")

        arduino.write(CALIBRATION_WEIGHT)
        arduino.write(f"{calib_weight}\n".encode('utf-8'))
        print(f"[calibrate_scale] Sent CALIBRATION_WEIGHT and value {calib_weight} to Arduino")

        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE after sending weight")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE after sending weight")
                    break

        arduino.write(CALIBRATION_CONTINUE)
        print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino for Step 3")

        print("Step 3: Calculating calibration value, please wait...")
        new_calibration = None
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_WEIGHT:
                    try:
                        calib_line = arduino.readline().decode('utf-8', errors='replace').strip()
                        new_calibration = float(calib_line)
                        print(f"[calibrate_scale] Received new calibration value: {new_calibration}")
                        break
                    except Exception as e:
                        logging.error(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")
                        print(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")

        print(f"[calibrate_scale] Saving calibration value {new_calibration} for station {station_id}")
        write_station_calibration(config_file, station_id, new_calibration)
        print("[calibrate_scale] Calibration complete.")

    except Exception as e:
        logging.error(f"[calibrate_scale] Unexpected error: {e}")
        print(f"[calibrate_scale] Unexpected error: {e}")

def tare_scale(station_id, arduino):
    try:
        arduino.write(TARE_SCALE)
        arduino.flush()
        print(f"Sent TARE_SCALE command to station {station_id}")
    except serial.SerialException as e:
        logging.error(f"Error communicating with station {station_id}: {e}")
        print(f"Error communicating with station {station_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in tare_scale: {e}")
        print(f"Unexpected error in tare_scale: {e}")

def clear_serial_buffer(ser):
    while ser.in_waiting:
        ser.read(ser.in_waiting)

if __name__ == "__main__":
    arduinos, port_labels = scan_arduinos_by_station_id()
    if not arduinos:
        print("No Arduino stations found.")
        sys.exit(1)

    print("Detected Arduino stations:")
    for station_id in sorted(port_labels):
        print(f"  station{station_id}: {port_labels[station_id]}")

    print("\nUsage:")
    print("  python scaleCalibration.py calibrate <station_id>")
    print("  python scaleCalibration.py tare <station_id>")
    print("Example: python scaleCalibration.py calibrate 3\n")

    if len(sys.argv) < 3:
        sys.exit(0)

    command = sys.argv[1].lower()
    try:
        station_id = int(sys.argv[2])
        if station_id not in arduinos:
            print("Invalid station_id. See detected stations above.")
            sys.exit(1)
    except ValueError:
        print("Invalid station_id. Must be an integer.")
        sys.exit(1)

    arduino = arduinos[station_id]
    if command == "calibrate":
        calibrate_scale(station_id, arduino)
    elif command == "tare":
        tare_scale(station_id, arduino)
    else:
        print("Unknown command.")
        sys.exit(1)
