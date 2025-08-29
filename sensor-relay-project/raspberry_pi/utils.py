import logging
import os
from config import (
    DEBUG,
    NUM_STATIONS,
    config_file,
    BOTTLE_WEIGHT_TOLERANCE,
    # ...any other constants you use
)

def update_station_status(app, station_index, weight, filling_mode, is_filling, fill_result=None, fill_time=None):
    """
    Update the status label for a station.
    'weight' should be the final fill weight if called from handle_final_weight.
    """
    print(f"[DEBUG] update_station_status: idx={station_index}, weight={weight}, mode={filling_mode}, is_filling={is_filling}, fill_result={fill_result}, fill_time={fill_time}")
    widget = app.station_widgets[station_index]
    print(f"widget for station {station_index} is {widget}")
    units = getattr(app, "units", "g")
    tr = getattr(app, "tr", lambda k: k)
    if filling_mode == "AUTO":
        if fill_result == "complete":
            if units == "oz":
                weight_str = f"{weight / 28.3495:.2f} oz"
            else:
                weight_str = f"{weight} g"
            if fill_time is not None:
                status_text = f"{tr('FINAL WEIGHT')}: {weight_str}\n{tr('TIME')}: {fill_time:.2f} s"
                widget.set_status(status_text, color="#11BD33")
            else:
                status_text = f"{tr('FINAL WEIGHT')}: {weight_str}"
                widget.set_status(status_text, color="#11BD33")
        elif fill_result == "timeout":
            if units == "oz":
                weight_str = f"{weight / 28.3495:.2f} oz"
            else:
                weight_str = f"{weight} g"
            if fill_time is not None:
                status_text = f"{tr('TIMEOUT')}\n{tr('FINAL WEIGHT')}: {weight_str}\n{tr('TIME')}: {fill_time:.2f} s"
                widget.set_status(status_text, color="#F6EB61")
            else:
                status_text = f"{tr('TIMEOUT')}\n{tr('FINAL WEIGHT')}: {weight_str}"
                widget.set_status(status_text, color="#F6EB61")
        elif fill_result is None and is_filling:
            widget.set_status(tr("AUTO FILL RUNNING"), color="#F6EB61")
        elif weight < 40:
            widget.set_status(tr("AUTO FILL READY"), color="#11BD33")
        else:
            widget.set_status(tr("READY"), color="#fff")
    else:
        widget.set_status(tr("READY"), color="#fff")

# ========== UTILITY FUNCTIONS ==========
def load_scale_calibrations():
    """Load scale calibration values from config.txt into the global scale_calibrations list."""
    global scale_calibrations
    calibrations = [1.0] * NUM_STATIONS
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, "r") as file:
            for line in file:
                if line.startswith("station") and "_calibration=" in line:
                    key, value = line.strip().split("=")
                    station_num = int(key.replace("station", "").replace("_calibration", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        calibrations[station_num - 1] = float(value)
    except FileNotFoundError:
        logging.error(f"{config_file} not found. Using default calibration values.")
    except Exception as e:
        logging.error(f"Error reading {config_file}: {e}")
    scale_calibrations = calibrations
    if DEBUG:
        print(f"Loaded scale calibration values: {scale_calibrations}")
    return calibrations

def load_station_enabled(config_path):
    enabled = [False] * NUM_STATIONS
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                for i in range(NUM_STATIONS):
                    key = f"station{i+1}_enabled="
                    if line.startswith(key):
                        value = line.split("=")[1].strip().lower()
                        enabled[i] = value == "true"
                        if DEBUG:
                            print(f"[DEBUG] Found {key}{value} -> enabled[{i}] = {enabled[i]}")
    except Exception as e:
        if DEBUG:
            print(f"Error reading station_enabled from config: {e}")
    if DEBUG:
        print(f"[DEBUG] Final enabled list: {enabled}")
    return enabled

def save_station_enabled(config_path, station_enabled):
    try:
        with open(config_path, "r") as f:
            lines = f.readlines()
        with open(config_path, "w") as f:
            for line in lines:
                written = False
                for i in range(NUM_STATIONS):
                    key = f"station{i+1}_enabled="
                    if line.strip().startswith(key):
                        f.write(f"{key}{'true' if station_enabled[i] else 'false'}\n")
                        written = True
                        break
                if not written:
                    f.write(line)
    except Exception as e:
        if DEBUG:
            print(f"Error writing station_enabled to config: {e}")

def load_station_serials():
    serials = [None] * NUM_STATIONS
    config_path = os.path.join(os.path.dirname(__file__), config_file)
    try:
        with open(config_path, "r") as file:
            for line in file:
                if line.startswith("station") and "_serial=" in line:
                    key, value = line.strip().split("=")
                    station_num = int(key.replace("station", "").replace("_serial", ""))
                    if 1 <= station_num <= NUM_STATIONS:
                        serials[station_num - 1] = value
    except Exception as e:
        logging.error(f"Error reading serials from config: {e}")
    return serials

def load_bottle_sizes(config_path):
    bottle_sizes = {}
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("bottle_"):
                    key, value = line.split("=")
                    name = key.replace("bottle_", "")
                    parts = value.split(":")
                    if len(parts) == 3:
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        default_time_limit = int(parts[2])
                        bottle_sizes[name] = (full_weight, empty_weight, default_time_limit)
                    elif len(parts) == 2:
                        # fallback for old format
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        bottle_sizes[name] = (full_weight, empty_weight, None)
    except Exception as e:
        if DEBUG:
            print(f"Error loading bottle sizes: {e}")
    if DEBUG:
        print(f"[DEBUG] Loaded bottle sizes: {bottle_sizes}")
    return bottle_sizes

def load_bottle_weight_ranges(config_path, tolerance=BOTTLE_WEIGHT_TOLERANCE):
    bottle_ranges = {}
    try:
        with open(config_path, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("bottle_"):
                    key, value = line.split("=")
                    name = key.replace("bottle_", "")
                    parts = value.split(":")
                    if len(parts) >= 2:
                        full_weight = float(parts[0])
                        empty_weight = float(parts[1])
                        bottle_ranges[name] = {
                            "full": (full_weight - tolerance, full_weight + tolerance),
                            "empty": (empty_weight - tolerance, empty_weight + tolerance)
                        }
                        # Optionally store time limit if present
                        if len(parts) == 3:
                            bottle_ranges[name]["default_time_limit"] = int(parts[2])
    except Exception as e:
        if DEBUG:
            print(f"Error loading bottle weight ranges: {e}")
    return bottle_ranges

def clear_serial_buffer(arduino):
    """Read and discard all available bytes from the Arduino serial buffer."""
    while arduino.in_waiting > 0:
        arduino.read(arduino.in_waiting)