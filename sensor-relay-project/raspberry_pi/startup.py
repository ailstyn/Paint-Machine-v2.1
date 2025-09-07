import time
import logging
import config
import serial
import re
import traceback
from config import GPIO

from utils import (
    load_scale_calibrations,
    load_station_enabled,
    save_station_enabled,
    load_station_serials,
    load_bottle_sizes,
    load_bottle_weight_ranges,
    clear_serial_buffer,
)

def get_current_station_weights(context):
    """
    Returns a list of current weights for all enabled and connected stations.
    Uses context['station_weights'] if available, else returns zeros.
    """
    NUM_STATIONS = context.get('NUM_STATIONS', 4)
    station_enabled = context.get('station_enabled', [True]*NUM_STATIONS)
    station_connected = context.get('station_connected', [True]*NUM_STATIONS)
    station_weights = context.get('station_weights', [0]*NUM_STATIONS)
    return [station_weights[i] for i in range(NUM_STATIONS) if station_enabled[i] and station_connected[i]]

def step_load_serials_and_ranges(context):
    try:
        print("Step: Load serials, bottle sizes, ranges, and calibration values")
        # Load serials
        context['station_serials'] = load_station_serials()
        # Load bottle sizes and ranges
        context['bottle_sizes'] = load_bottle_sizes(context['config_file'])
        context['bottle_ranges'] = load_bottle_weight_ranges(context['config_file'], tolerance=context.get('BOTTLE_WEIGHT_TOLERANCE', 25))
        # Load calibration values
        context['scale_calibrations'] = load_scale_calibrations()
        print(f"[DEBUG] Loaded serials: {context['station_serials']}")
        print(f"[DEBUG] Loaded bottle sizes: {context['bottle_sizes']}")
        print(f"[DEBUG] Loaded bottle ranges: {context['bottle_ranges']}")
        print(f"[DEBUG] Loaded scale calibrations: {context['scale_calibrations']}")
        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_load_serials_and_ranges: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_load_serials_and_ranges: {e}")


def step_connect_arduinos(context):
    try:
        print("Step: Connect and initialize Arduinos")
        NUM_STATIONS = context['NUM_STATIONS']
        station_serials = context['station_serials']
        scale_calibrations = context['scale_calibrations']
        config = context['config']
        DEBUG = context.get('DEBUG', False)

        print(f"[DEBUG] NUM_STATIONS: {NUM_STATIONS}")
        print(f"[DEBUG] station_serials: {station_serials}")
        print(f"[DEBUG] scale_calibrations: {scale_calibrations}")
        print(f"[DEBUG] arduino_ports: {getattr(config, 'arduino_ports', [])}")

        station_connected = [False] * NUM_STATIONS
        arduinos = [None] * NUM_STATIONS

        for port in getattr(config, 'arduino_ports', []):
            try:
                print(f"[DEBUG] Trying port {port}...")
                arduino = serial.Serial(port, 9600, timeout=0.5)
                # Send RESET_HANDSHAKE before PMID to allow handshake restart
                arduino.write(config.RESET_HANDSHAKE)
                arduino.flush()
                time.sleep(0.05)
                for b in b'PMID':
                    arduino.write(bytes([b]))
                    arduino.flush()
                    time.sleep(0.01)
                station_serial_number = None
                for _ in range(60):
                    if arduino.in_waiting > 0:
                        line = arduino.read_until(b'\n').decode(errors='replace').strip()
                        print(f"[DEBUG] Received from {port}: {repr(line)}")
                        match = re.search(r"SN\d{3,4}", line)
                        if match:
                            serial_match = re.search(r"<SERIAL:([A-Z\-]*SN\d{3,4})>", line)
                            if serial_match:
                                station_serial_number = serial_match.group(1)
                            else:
                                station_serial_number = match.group(0)
                            print(f"[DEBUG] Station serial {station_serial_number} detected on {port}")
                            arduino.write(config.CONFIRM_ID)
                            arduino.flush()
                            print(f"[DEBUG] Sent CONFIRM_ID to station on port {port}")
                            break
                    time.sleep(0.1)
                matched_entry = None
                if station_serial_number is not None:
                    for entry in station_serials:
                        if station_serial_number in entry:
                            matched_entry = entry
                            break
                if matched_entry is None:
                    if DEBUG:
                        print(f"[DEBUG] No recognized station detected on port {port}, skipping...")
                    arduino.close()
                    continue
                station_index = station_serials.index(matched_entry)
                got_request = False
                for _ in range(40):
                    if arduino.in_waiting > 0:
                        req = arduino.read(1)
                        if req == config.REQUEST_CALIBRATION:
                            if DEBUG:
                                print(f"[DEBUG] Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {scale_calibrations[station_index]}")
                            arduino.write(config.REQUEST_CALIBRATION)
                            arduino.write(f"{scale_calibrations[station_index]}\n".encode('utf-8'))
                            got_request = True
                            break
                        else:
                            arduino.reset_input_buffer()
                    time.sleep(0.1)
                if not got_request:
                    if DEBUG:
                        print(f"[DEBUG] Station {station_index+1}: Did not receive calibration request, skipping.")
                    arduino.close()
                    continue
                arduinos[station_index] = arduino
                station_connected[station_index] = True
                if DEBUG:
                    print(f"[DEBUG] Station {station_index+1} on {port} initialized and ready.")
            except Exception as e:
                logging.error(f"Error initializing Arduino on {port}: {e}")
                if DEBUG:
                    print(f"[DEBUG] Error initializing Arduino on {port}: {e}")

        context['station_connected'] = station_connected
        context['arduinos'] = arduinos
        print(f"[DEBUG] Final station_connected: {context['station_connected']}")
        print(f"[DEBUG] Final arduinos: {context['arduinos']}")
        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_connect_arduinos: {e}")
        print(f"[ERROR] Exception in step_connect_arduinos: {e}")


def step_station_verification(context):
    try:
        wizard = context['wizard']
        app = context['app']
        NUM_STATIONS = context['NUM_STATIONS']
        station_connected = context.get('station_connected', [True] * NUM_STATIONS)
        # Always use the latest context['station_enabled']
        wizard.set_station_labels(
            names=[f"Station {i+1}" for i in range(NUM_STATIONS)],
            connected=station_connected,
            enabled=context['station_enabled']
        )
        print(f"[DEBUG] startup.py: set_station_labels enabled={context['station_enabled']}")

        step_result = {}

        def on_step_completed(info):
            step_result.clear()
            step_result.update(info)

        # Connect the signal/callback
        wizard.step_completed.connect(on_step_completed)

        wizard.show_station_verification()
        wizard.show()
        while not step_result or step_result.get("step") != "station_verification":
            app.processEvents()
            time.sleep(0.01)

        # Save the enabled/disabled stations to context as soon as user continues
        if "enabled" in step_result:
            context['station_enabled'] = step_result["enabled"]
        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_station_verification: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_station_verification: {e}")
        return


def step_tare_scales(context):
    try:
        print("Step: Send TARE_SCALE to Arduinos")
        arduinos = context.get('arduinos', [])
        station_enabled = context.get('station_enabled', [])
        station_connected = context.get('station_connected', [])
        config = context.get('config')

        # Send TARE_SCALE to each enabled and connected Arduino
        for i, arduino in enumerate(arduinos):
            if arduino and station_enabled[i] and station_connected[i]:
                try:
                    arduino.write(config.TARE_SCALE)
                    arduino.flush()
                    print(f"[DEBUG] Sent TARE_SCALE to station {i+1}")
                except Exception as e:
                    logging.error(f"Error sending TARE_SCALE to station {i+1}: {e}")
                    print(f"[ERROR] Error sending TARE_SCALE to station {i+1}: {e}")

        context['tare_sent'] = True
        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_tare_scales: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_tare_scales: {e}")
        return 'error'


def step_filling_mode_selection(context):
    try:
        app = context['app']
        wizard = context['wizard']
        SelectionDialog = context['SelectionDialog']
        InfoDialog = context['InfoDialog']
        Qt = context['Qt']
        QTimer = context['QTimer']
        logging = context['logging']
        filling_mode_callback = context['filling_mode_callback']

        options = [
            ("AUTO", "Auto Mode"),
            ("MANUAL", "Manual Mode"),
            ("SMART", "Smart Mode")
        ]
        print("[DEBUG] Creating filling mode SelectionDialog...")

        try:
            selection_dialog = SelectionDialog(options=options, title="FILLING MODE")
            selection_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            selection_dialog.show()
            app.active_dialog = selection_dialog

            filling_mode_selected = None
            def on_select(mode, index):
                nonlocal filling_mode_selected
                filling_mode_selected = mode
                try:
                    filling_mode_callback(mode)
                except Exception as e:
                    logging.error(f"Error in filling_mode_callback: {e}")
                    print(f"[ERROR] Exception in filling_mode_callback: {e}")
                selection_dialog.accept()
            selection_dialog.on_select_callback = on_select

            while selection_dialog.isVisible():
                app.processEvents()
                time.sleep(0.01)
            print("[DEBUG] SelectionDialog no longer visible.")
        except Exception as e:
            logging.error(f"Exception during filling mode dialog: {e}")
            print(f"[ERROR] Exception during filling mode dialog: {e}")

        app.active_dialog = wizard
        context['filling_mode'] = filling_mode_selected

        # Handle MANUAL mode early exit
        if filling_mode_selected == "MANUAL":
            try:
                info_dialog = InfoDialog(
                    app.tr("Manual Mode Selected") if hasattr(app, 'tr') else "Manual Mode Selected",
                    app.tr("Manual mode selected. You will control filling manually.") if hasattr(app, 'tr') else "Manual mode selected. You will control filling manually.",
                    wizard
                )
                info_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                info_dialog.show()
                QTimer.singleShot(2500, info_dialog.accept)
                while info_dialog.isVisible():
                    app.processEvents()
                    time.sleep(0.01)
                wizard.finish_wizard()
                app.active_dialog = app
                context['after_startup']()  # Call the after_startup callback
                return 'manual_selected'    # Special result for early exit
            except Exception as e:
                logging.error(f"Error during manual mode info dialog: {e}")
                print(f"[ERROR] Exception during manual mode info dialog: {e}")
                return 'error'

        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_filling_mode_selection: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_filling_mode_selection: {e}")
        return 'error'


def step_clear_all_scales(context):
    wizard = context['wizard']
    app = context['app']
    NUM_STATIONS = context['NUM_STATIONS']
    station_enabled = context['station_enabled']
    station_connected = context['station_connected']
    arduinos = context['arduinos']
    config = context['config']
    step_result = {}

    def on_step_completed(info):
            print("[DEBUG] step_clear_all_scales: on_step_completed called with info:", info)
            step_result.clear()
            step_result.update(info)
    wizard.step_completed.connect(on_step_completed)
    print("[DEBUG] step_clear_all_scales: wizard.step_completed.connect(on_step_completed) called")

    while True:
        wizard.show_empty_scale_prompt()
        wizard.show()
        while not step_result or step_result.get("step") != "empty_scale":
            app.processEvents()
            time.sleep(0.01)

        action = step_result.get("action")
        print(f"[DEBUG] step_clear_all_scales: action value is {action}")
        if action == "backup":
            return 'backup'  # Signal to main sequence to go back one step
        elif action == "accept":
            print("[DEBUG] step_clear_all_scales: action == 'accept' reached")
            scale_values = get_current_station_weights(context)
            if any(w > 20 for w in scale_values):
                options = [("NO", "NO"), ("YES", "YES")]
                selection_dialog = context['SelectionDialog'](options=options, title="Are the scales clear?")
                selection_dialog.selected_index = 0
                selection_dialog.setWindowModality(context['Qt'].WindowModality.ApplicationModal)
                selection_dialog.show()
                app.active_dialog = selection_dialog
                user_choice = None
                def on_select(opt, idx):
                    nonlocal user_choice
                    user_choice = opt
                    selection_dialog.accept()
                selection_dialog.on_select_callback = on_select
                while selection_dialog.isVisible():
                    app.processEvents()
                    time.sleep(0.01)
                app.active_dialog = wizard
                if user_choice == "YES":
                    print("[DEBUG] step_clear_all_scales: break reached, moving to tare scales")
                    break
                else:
                    step_result.clear()
                    continue
            else:
                print("[DEBUG] step_clear_all_scales: break reached, moving to tare scales")
                break
        else:
            # Unknown action, just continue loop
            step_result.clear()
            continue

    # Send TARE_SCALE to each enabled and connected Arduino
    for i, arduino in enumerate(arduinos):
        if arduino and station_enabled[i] and station_connected[i]:
            try:
                arduino.write(config.TARE_SCALE)
                arduino.flush()
            except Exception as e:
                context['logging'].error(f"Error sending TARE_SCALE to station {i+1}: {e}")

    print("[DEBUG] step_clear_all_scales: break reached, moving to tare scales")
    return 'completed'


def step_full_bottle_check(context):
    try:
        app = context['app']
        wizard = context['wizard']
        InfoDialog = context['InfoDialog']
        Qt = context['Qt']
        QTimer = context['QTimer']
        ping_buzzer_invalid = context['ping_buzzer_invalid']
        NUM_STATIONS = context['NUM_STATIONS']
        station_enabled = context['station_enabled']
        station_connected = context['station_connected']
        config_file = context['config_file']
        DEBUG = context.get('DEBUG', False)

        # Load all bottle ranges from config.txt
        bottle_ranges = load_bottle_weight_ranges(config_file, tolerance=context.get('BOTTLE_WEIGHT_TOLERANCE', 25))
        context['bottle_ranges'] = bottle_ranges  # Update context in case other steps use it

        full_ranges = {name: bottle_ranges[name]["full"] for name in bottle_ranges}

        wizard.show_full_bottle_prompt(full_ranges)
        wizard.update_weight_labels_for_full_bottle(full_ranges)
        wizard.show()
        step_result = {}

        def on_step_completed(info):
            step_result.clear()
            step_result.update(info)
        wizard.step_completed.connect(on_step_completed)

        selected_bottle_id = None
        while True:
            while not step_result or step_result.get("step") != "full_bottle":
                app.processEvents()
                time.sleep(0.01)
                wizard.update_weight_labels_for_full_bottle(full_ranges)

            action = step_result.get("action")
            if action == "accept":
                active_weights = get_current_station_weights(context)

                def in_range(w, rng):
                    return rng[0] <= w <= rng[1]

                found = False
                for bottle_id, rng in full_ranges.items():
                    if all(in_range(w, rng) for w in active_weights):
                        selected_bottle_id = bottle_id
                        found = True
                        break

                if not found:
                    try:
                        dlg = InfoDialog(
                            app.tr("Error") if hasattr(app, 'tr') else "Error",
                            app.tr("All bottles must be within the same size range.") if hasattr(app, 'tr') else "All bottles must be within the same size range.",
                            wizard
                        )
                        ping_buzzer_invalid()
                        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
                        dlg.show()
                        QTimer.singleShot(3000, dlg.accept)
                        step_result.clear()  # Let user try again
                        continue
                    except Exception as e:
                        logging.error(f"Error showing InfoDialog in step_full_bottle_check: {e}")
                        print(f"[ERROR] Error showing InfoDialog in step_full_bottle_check: {e}")
                        return 'error'
                else:
                    break  # Proceed to next step
            else:
                step_result.clear()
                continue

        # Set target_weight and time_limit based on selected bottle
        target_weight = None
        time_limit = None
        if selected_bottle_id:
            try:
                bottle_config_line = None
                with open(config_file, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f"bottle_{selected_bottle_id}"):
                            bottle_config_line = line
                            break
                if bottle_config_line:
                    parts = bottle_config_line.split("=")[1].split(":")
                    if len(parts) >= 3:
                        target_weight = float(parts[0])
                        time_limit = int(parts[2])
                        if DEBUG:
                            print(f"[DEBUG] Set target_weight to {target_weight} and time_limit to {time_limit} for bottle {selected_bottle_id}")
            except Exception as e:
                logging.error(f"Error parsing bottle config for {selected_bottle_id} in step_full_bottle_check: {e}")
                print(f"[ERROR] Error parsing bottle config for {selected_bottle_id} in step_full_bottle_check: {e}")
                return 'error'

        context['selected_bottle_id'] = selected_bottle_id
        context['target_weight'] = target_weight
        context['time_limit'] = time_limit

        wizard.show_empty_bottle_prompt()
        wizard.show()

        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_full_bottle_check: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_full_bottle_check: {e}")
        return 'error'


def step_empty_bottle_check(context):
    try:
        app = context['app']
        wizard = context['wizard']
        InfoDialog = context['InfoDialog']
        Qt = context['Qt']
        QTimer = context['QTimer']
        ping_buzzer_invalid = context['ping_buzzer_invalid']
        NUM_STATIONS = context['NUM_STATIONS']
        station_enabled = context['station_enabled']
        station_connected = context['station_connected']
        bottle_ranges = context['bottle_ranges']
        selected_bottle_id = context['selected_bottle_id']
        config_file = context['config_file']
        DEBUG = context.get('DEBUG', False)
        after_startup = context.get('after_startup')

        if selected_bottle_id and selected_bottle_id in bottle_ranges:
            empty_range = bottle_ranges[selected_bottle_id]["empty"]
        else:
            empty_range = (0, 0)

        wizard.show_empty_bottle_prompt(empty_range=empty_range)
        wizard.update_weight_labels_for_empty_bottle(empty_range)
        wizard.show()
        step_result = {}

        while True:
            step_result.clear()
            while not step_result or step_result.get("step") != "empty_bottle":
                app.processEvents()
                time.sleep(0.01)
                wizard.update_weight_labels_for_empty_bottle(empty_range)

            active_weights = get_current_station_weights(context)

            def in_range(w, rng):
                return rng[0] <= w <= rng[1]

            if not all(in_range(w, empty_range) for w in active_weights):
                try:
                    dlg = InfoDialog(
                        app.tr("Error") if hasattr(app, 'tr') else "Error",
                        app.tr("All bottles must be within the empty bottle weight range.") if hasattr(app, 'tr') else "All bottles must be within the empty bottle weight range.",
                        wizard
                    )
                    ping_buzzer_invalid()
                    dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
                    dlg.show()
                    QTimer.singleShot(2000, dlg.accept)
                    continue
                except Exception as e:
                    logging.error(f"Error showing InfoDialog in step_empty_bottle_check: {e}")
                    print(f"[ERROR] Error showing InfoDialog in step_empty_bottle_check: {e}")
                    return 'error'
            else:
                bottle_config_line = None
                try:
                    with open(config_file, "r") as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith(f"bottle_{selected_bottle_id}"):
                                bottle_config_line = line
                                break
                    if bottle_config_line:
                        parts = bottle_config_line.split("=")[1].split(":")
                        try:
                            context['target_weight'] = float(parts[0])
                            if len(parts) >= 3:
                                context['time_limit'] = int(parts[2])
                            else:
                                context['time_limit'] = 3000
                            if DEBUG:
                                print(f"[DEBUG] (empty bottle step) Set target_weight to {context['target_weight']} and time_limit to {context['time_limit']} for bottle {selected_bottle_id}")
                        except Exception as e:
                            logging.error(f"Error parsing bottle config for {selected_bottle_id} in step_empty_bottle_check: {e}")
                            print(f"[ERROR] Error parsing bottle config for {selected_bottle_id} in step_empty_bottle_check: {e}")
                    if after_startup:
                        after_startup()
                    wizard.finish_wizard()
                    app.active_dialog = app
                    break
                except Exception as e:
                    logging.error(f"Error finalizing step_empty_bottle_check: {e}")
                    print(f"[ERROR] Error finalizing step_empty_bottle_check: {e}")
                    return 'error'
        return 'completed'
    except Exception as e:
        logging.error(f"Error in step_empty_bottle_check: {e}\n{traceback.format_exc()}")
        print(f"[ERROR] Exception in step_empty_bottle_check: {e}")
        return 'error'


# Pre-startup steps: run before main startup sequence
prestartup_steps = [
    step_load_serials_and_ranges,
    step_connect_arduinos,
]

# Main startup steps: run after globals are updated
startup_steps = [
    step_station_verification,
    step_clear_all_scales,
    step_filling_mode_selection,
    step_full_bottle_check,
    step_empty_bottle_check,
]

def run_startup_sequence(context):
    step_index = 0
    steps_total = len(startup_steps)
    print(f"[DEBUG] Starting startup sequence. Total steps: {steps_total}")
    while 0 <= step_index < steps_total:
        step_func = startup_steps[step_index]
        print(f"[DEBUG] Running step {step_index+1}/{steps_total}: {step_func.__name__}")
        try:
            result = step_func(context)
            print(f"[DEBUG] Step {step_func.__name__} returned: {result}")
        except Exception as e:
            logging.error(f"Error in step {step_func.__name__}: {e}")
            print(f"[ERROR] Exception in step {step_func.__name__}: {e}")
            break
        if result == 'completed':
            step_index += 1
        elif result == 'backup':
            step_index -= 1
            print(f"[DEBUG] User requested backup. Moving to step {step_index+1}")
        elif result == 'manual_selected':
            print("[DEBUG] Manual mode selected, exiting startup sequence early.")
            break
        else:
            print(f"[ERROR] Unknown result: {result}. Exiting sequence.")
            logging.error(f"Unknown result from step {step_func.__name__}: {result}")
            break
    print("[DEBUG] Startup sequence finished.")
    
"""
if __name__ == "__main__":
    wizard = StartupWizardDialog()
    app = None  # Replace with actual app instance
    context = {'wizard': wizard, 'app': app}
    run_startup_sequence(context)

    from startup import step_clear_all_scales

    context = {
        'wizard': wizard,
        'app': app,
        'NUM_STATIONS': NUM_STATIONS,
        'station_enabled': station_enabled,
        'station_connected': station_connected,
        'arduinos': arduinos,
        'config': config,
        'SelectionDialog': SelectionDialog,
        'Qt': Qt,
        'logging': logging,
    }

    result = step_filling_mode_selection(context)
    if result == 'manual_selected':
        import sys
        sys.exit()  # Exits the script early"""