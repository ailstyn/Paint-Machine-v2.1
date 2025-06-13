import sys
import logging

def write_scale_calibrations():
    # Write scale calibration values to the config file
    try:
        with open(config_file, "w") as file:
            for value in scale_calibrations:
                file.write(f"{value}\n")
    except Exception as e:
        logging.error(f"Error writing to {config_file}: {e}")

def calibrate_scale(arduino_id, app):
    try:
        arduino = arduinos[arduino_id]
        print(f"[calibrate_scale] Starting calibration for Arduino {arduino_id}")

        arduino.write(RESET_CALIBRATION)
        arduino.flush()
        print("[calibrate_scale] Sent RESET_CALIBRATION to Arduino")

        # Step 1: Remove all weight from the scale
        app.show_dialog_content(
            title=LANGUAGES[app.language]["CALIBRATION_TITLE"],
            message=LANGUAGES[app.language]["CALIBRATION_REMOVE_WEIGHT"]
        )
        print("[calibrate_scale] Step 1 dialog shown")

        while True:
            # Read current weight from Arduino
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CURRENT_WEIGHT:
                    try:
                        weight_line = arduino.readline().decode('utf-8', errors='replace').strip()
                        weight = float(weight_line)
                        app.set_current_weight_mode(weight)
                    except Exception as e:
                        logging.error(f"[calibrate_scale] Error parsing weight: {e}")
                        print(f"[calibrate_scale] Error parsing weight: {e}")

            QApplication.processEvents()

            # Check for SELECT button press
            if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                ping_buzzer()
                print("[calibrate_scale] SELECT pressed in Step 1")
                # Wait for button release to avoid double press
                while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                    QApplication.processEvents()
                    time.sleep(0.01)
                # Send CALIBRATION_CONTINUE to Arduino
                clear_serial_buffer(arduino)
                arduino.write(CALIBRATION_CONTINUE)
                arduino.flush()
                print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino")
                break

        # Wait for CALIBRATION_STEP_DONE from Arduino before proceeding to Step 2
        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE from Arduino")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE from Arduino")
                    break
            QApplication.processEvents()
            time.sleep(0.01)

        # --- Step 2: Place calibration weight and set value ---
        calib_weight = 100  # Default value in grams

        def update_display(value, *args, **kwargs):
            app.show_dialog_content(
                title=f"Calibration (Arduino {arduino_id+1})",
                message=LANGUAGES[app.language]["CALIBRATION_PLACE_WEIGHT"].format(value=value)
            )

        print("[calibrate_scale] Step 2 dialog shown")
        update_display(calib_weight)

        calib_weight = adjust_value_with_acceleration(
            initial_value=calib_weight,
            dialog=type('DialogStub', (), {
                'update_value': staticmethod(update_display),
                'accept': staticmethod(lambda *args, **kwargs: None),
                'close': staticmethod(lambda *args, **kwargs: None)
            })(),
            up_button_pin=UP_BUTTON_PIN,
            down_button_pin=DOWN_BUTTON_PIN,
            unit_increment=1,
            min_value=0,
            up_callback=update_display,
            down_callback=update_display
        )
        print(f"[calibrate_scale] Calibration weight set to {calib_weight}")

        # Wait for SELECT button press in Step 2
        while True:
            QApplication.processEvents()
            time.sleep(0.01)
            if GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                ping_buzzer()
                print("[calibrate_scale] SELECT pressed in Step 2")
                # Wait for button release to avoid double press
                while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
                    QApplication.processEvents()
                    time.sleep(0.01)
                # Send CALIBRATION_WEIGHT byte and value to Arduino
                arduino.write(CALIBRATION_WEIGHT)
                arduino.write(f"{calib_weight}\n".encode('utf-8'))
                print(f"[calibrate_scale] Sent CALIBRATION_WEIGHT and value {calib_weight} to Arduino")
                break

        # Wait for CALIBRATION_STEP_DONE from Arduino before proceeding
        print("[calibrate_scale] Waiting for CALIBRATION_STEP_DONE after sending weight")
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_STEP_DONE:
                    print("[calibrate_scale] Received CALIBRATION_STEP_DONE after sending weight")
                    break
            QApplication.processEvents()
            time.sleep(0.01)

        # Send CALIBRATION_CONTINUE to Arduino to proceed to the next step
        arduino.write(CALIBRATION_CONTINUE)
        print("[calibrate_scale] Sent CALIBRATION_CONTINUE to Arduino for Step 3")

        # --- Step 3: Wait for calibration value from Arduino ---
        app.show_dialog_content(
            title=f"Calibration (Arduino {arduino_id+1})",
            message=LANGUAGES[app.language]["CALIBRATION_CALCULATING"]
        )
        print("[calibrate_scale] Step 3 dialog shown, waiting for CALIBRATION_WEIGHT from Arduino")

        new_calibration = None
        while True:
            if arduino.in_waiting > 0:
                msg_type = arduino.read(1)
                if msg_type == CALIBRATION_WEIGHT:
                    # Read the calibration value sent as a string (e.g., "427.53\n")
                    try:
                        calib_line = arduino.readline().decode('utf-8', errors='replace').strip()
                        new_calibration = float(calib_line)
                        print(f"[calibrate_scale] Received new calibration value: {new_calibration}")
                        break
                    except Exception as e:
                        logging.error(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")
                        print(f"[calibrate_scale] Failed to parse calibration value from Arduino: {e}")
            QApplication.processEvents()
            time.sleep(0.01)

        # Save the new calibration value for this Arduino
        scale_calibrations[arduino_id] = new_calibration
        print(f"[calibrate_scale] Saving calibration value {new_calibration} for Arduino {arduino_id}")
        write_scale_calibrations()

        # Confirmation dialog
        app.show_dialog_content(
            title=LANGUAGES[app.language]["CALIBRATION_COMPLETE_TITLE"],
            message=LANGUAGES[app.language]["CALIBRATION_COMPLETE_MSG"].format(value=new_calibration)
        )
        print("[calibrate_scale] Calibration complete dialog shown")
        # Wait for SELECT to finish
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
            QApplication.processEvents()
            time.sleep(0.01)
        ping_buzzer()
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            QApplication.processEvents()
            time.sleep(0.01)

        app.clear_dialog_content()
        print("[calibrate_scale] Calibration process finished and UI reset")

    except Exception as e:
        logging.error(f"[calibrate_scale] Unexpected error: {e}")
        print(f"[calibrate_scale] Unexpected error: {e}")
        
def tare_scale(arduino_id):
#     arduino_id: The ID of the Arduino to send the tare command to.

    if arduino_id < 0 or arduino_id >= len(arduinos):
        logging.error(f"Invalid Arduino ID: {arduino_id}")
        return

    try:
        arduino = arduinos[arduino_id]
        arduino.write(TARE_SCALE)  # Send the tare command
        print(f"Sent TARE_SCALE command to Arduino {arduino_id}")
    except serial.SerialException as e:
        logging.error(f"Error communicating with Arduino {arduino_id}: {e}")

def print_usage():
    print("Usage:")
    print("  python scaleCalibration.py calibrate <arduino_id>")
    print("  python scaleCalibration.py tare <arduino_id>")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()
    try:
        arduino_id = int(sys.argv[2])
    except ValueError:
        print("Invalid arduino_id. Must be an integer.")
        sys.exit(1)

    if command == "calibrate":
        calibrate_scale(arduino_id, app=None)  # Pass your app or None if not needed
    elif command == "tare":
        tare_scale(arduino_id)
    else:
        print_usage()
        sys.exit(1)
