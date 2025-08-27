import config
import logging
from utils import update_station_status
from config import (
    NUM_STATIONS,
    config_file,
    target_weight,
    time_limit,
    scale_calibrations,
    DEBUG,
    E_STOP,
    PREV_E_STOP_STATE,
    FILL_LOCKED,
    last_fill_time,
    last_final_weight,
    fill_time_limit_reached,
    SESSION_ID,
    arduinos,
    station_connected,
    serial_numbers,
    filling_mode,
    station_max_weight_error,
    BOTTLE_WEIGHT_TOLERANCE,
    RELAY_POWER_ENABLED,
)

# ========== MESSAGE HANDLERS ==========
def handle_request_target_weight(station_index, arduino, **ctx):
    try:
        # Reject fill requests until relay power is enabled
        if not config.RELAY_POWER_ENABLED:
            if config.DEBUG:
                print(f"Station {station_index+1}: Fill request rejected, relay power not enabled yet. Sending STOP.")
            arduino.write(config.STOP)  # Send STOP to Arduino to abort fill
            return
        if ctx['FILL_LOCKED']:
            if config.DEBUG:
                print(f"Station {station_index+1}: Fill locked, sending STOP_FILL")
                print(f"Station {station_index+1}: Fill locked, sending STOP_FILL")
            arduino.write(config.STOP)
        else:
            arduino.write(config.TARGET_WEIGHT)
            arduino.write(f"{ctx['target_weight']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_target_weight", exc_info=True)

def handle_request_calibration(station_index, arduino, **ctx):
    try:
        if config.DEBUG:
            print(f"Station {station_index+1}: REQUEST_CALIBRATION received, sending calibration: {ctx['scale_calibrations'][station_index]}")
        arduino.write(config.REQUEST_CALIBRATION)
        arduino.write(f"{ctx['scale_calibrations'][station_index]}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_calibration", exc_info=True)

def handle_request_time_limit(station_index, arduino, **ctx):
    try:
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: REQUEST_TIME_LIMIT")
        arduino.write(config.REQUEST_TIME_LIMIT)
        arduino.write(f"{ctx['time_limit']}\n".encode('utf-8'))
    except Exception as e:
        logging.error("Error in handle_request_time_limit", exc_info=True)

def handle_current_weight(station_index, arduino, **ctx):
    try:
        weight_bytes = arduino.read(4)
        # print(f"[DEBUG][handle_current_weight] raw bytes: {weight_bytes!r}")
        if len(weight_bytes) == 4:
            weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            # print(f"[DEBUG][handle_current_weight] parsed weight: {weight}")
            widgets = ctx.get('station_widgets')
            app = ctx.get('app')
            target_weight = ctx.get('target_weight', 500.0)
            unit = getattr(app, "units", "g") if app else "g"
            if widgets:
                widget = widgets[station_index]
                if station_max_weight_error[station_index]:
                    widget.weight_label.setStyleSheet("color: #FF2222;")
                else:
                    widget.weight_label.setStyleSheet("color: #fff;")
                if hasattr(widget, "set_weight"):
                    widget.set_weight(weight, target_weight, unit)
                else:
                    if widget.weight_label:
                        if unit == "g":
                            widget.weight_label.setText(f"{int(round(weight))} g")
                        else:
                            oz = weight / 28.3495
                            widget.weight_label.setText(f"{oz:.1f} oz")
            # StartupWizardDialog support
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "StartupWizardDialog":
                # print(f"[DEBUG] Calling set_weight on StartupWizardDialog for station {station_index} with weight {weight}")
                ctx['active_dialog'].set_weight(station_index, weight)
        else:
            logging.error(f"Station {station_index}: Incomplete weight bytes received: {weight_bytes!r}")
            widgets = ctx.get('station_widgets')
            if widgets:
                widget = widgets[station_index]
                if widget.weight_label:
                    widget.weight_label.setText("0.0 g")
            if ctx['active_dialog'] is not None and ctx['active_dialog'].__class__.__name__ == "StartupWizardDialog":
                ctx['active_dialog'].set_weight(station_index, 0.0)
    except Exception as e:
        logging.error("Error in handle_current_weight", exc_info=True)

def handle_begin_auto_fill(station_index, arduino, **ctx):
    try:
        widgets = ctx['station_widgets']
        app = ctx.get('app')
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                if app:
                    widget.set_status(app.tr("AUTO FILL RUNNING"))
                else:
                    widget.set_status("AUTO FILL RUNNING")
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: BEGIN_AUTO_FILL received, status set.")
    except Exception as e:
        logging.error("Error in handle_begin_auto_fill", exc_info=True)

def handle_begin_smart_fill(station_index, arduino, **ctx):
    try:
        widgets = ctx['station_widgets']
        app = ctx.get('app')
        if widgets:
            widget = widgets[station_index]
            if hasattr(widget, "set_status"):
                if app:
                    widget.set_status(app.tr("SMART FILL RUNNING"))
                else:
                    widget.set_status("SMART FILL RUNNING")
        if ctx['DEBUG']:
            print(f"Station {station_index+1}: BEGIN_SMART_FILL received, status set.")
    except Exception as e:
        logging.error("Error in handle_begin_smart_fill", exc_info=True)

def handle_final_weight(station_index, arduino, **ctx):
    print(f"[DEBUG] handle_final_weight called for station {station_index}")
    try:
        weight_bytes = arduino.read(4)
        print(f"[DEBUG][handle_final_weight] raw bytes: {weight_bytes!r}")
        if len(weight_bytes) == 4:
            final_weight = int.from_bytes(weight_bytes, byteorder='little', signed=True)
            print(f"[DEBUG][handle_final_weight] parsed final_weight: {final_weight}")
            last_final_weight[station_index] = final_weight

            print("About to call update_station_status in handle_final_weight")
            update_station_status(
                ctx.get('app'),
                station_index,
                final_weight,  # Always use this value
                ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                is_filling=False,
                fill_result="complete",
                fill_time=None  # No time yet
            )

            fill_time = last_fill_time[station_index]
            if fill_time is not None:
                seconds = fill_time / 1000.0
                update_station_status(
                    ctx.get('app'),
                    station_index,
                    final_weight,
                    ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                    is_filling=False,
                    fill_result="complete",
                    fill_time=seconds
                )
                last_fill_time[station_index] = None
                last_final_weight[station_index] = None
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Final weight: {final_weight}")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Incomplete final weight bytes: {weight_bytes!r}")
    except Exception as e:
        logging.error("Error in handle_final_weight", exc_info=True)

def handle_fill_time(station_index, arduino, **ctx):
    try:
        time_bytes = arduino.read(4)
        if len(time_bytes) == 4:
            fill_time = int.from_bytes(time_bytes, byteorder='little', signed=False)
            last_fill_time[station_index] = fill_time
            final_weight = last_final_weight[station_index]
            if final_weight is not None:
                seconds = fill_time / 1000.0
                # If fill_time reached the time limit, treat as timeout
                if fill_time >= ctx.get('time_limit', 3000):
                    update_station_status(
                        ctx.get('app'),
                        station_index,
                        final_weight,
                        ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                        is_filling=False,
                        fill_result="timeout",
                        fill_time=seconds
                    )
                else:
                    update_station_status(
                        ctx.get('app'),
                        station_index,
                        final_weight,
                        ctx.get('app').filling_mode if ctx.get('app') else "AUTO",
                        is_filling=False,
                        fill_result="complete",
                        fill_time=seconds
                    )
                last_fill_time[station_index] = None
                last_final_weight[station_index] = None
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Fill time: {fill_time} ms")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Incomplete fill time bytes: {time_bytes!r}")
    except Exception as e:
        logging.error("Error in handle_fill_time", exc_info=True)

def handle_unknown(station_index, arduino, message_type, **ctx):
    try:
        if arduino.in_waiting > 0:
            extra = arduino.readline().decode('utf-8', errors='replace').strip()
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
            else:
                logging.error(f"Station {station_index+1}: Unknown message_type: {message_type!r}, extra: {extra!r}")
        else:
            if ctx['DEBUG']:
                print(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
            else:
                logging.error(f"Station {station_index+1}: Unknown message_type: {message_type!r}")
            if ctx['refresh_ui']:
                ctx['refresh_ui']()
    except Exception as e:
        logging.error("Error in handle_unknown", exc_info=True)

def handle_max_weight_warning(station_index, arduino, **ctx):
    widgets = ctx.get('station_widgets')
    app = ctx.get('app')
    station_max_weight_error[station_index] = True
    if widgets:
        widget = widgets[station_index]
        if hasattr(widget, "set_status"):
            if app:
                widget.set_status(f"<b>{app.tr('MAX WEIGHT EXCEEDED')}</b>", color="#FF2222", flashing=True)
            else:
                widget.set_status("<b>MAX WEIGHT EXCEEDED</b>", color="#FF2222", flashing=True)
    if DEBUG:
        print(f"[WARNING] Station {station_index+1}: MAX_WEIGHT_WARNING received")

def handle_max_weight_end(station_index, arduino, **ctx):
    widgets = ctx.get('station_widgets')
    station_max_weight_error[station_index] = False
    if widgets:
        widget = widgets[station_index]
        if hasattr(widget, "clear_status"):
            widget.clear_status()
        elif hasattr(widget, "set_status"):
            widget.set_status("")  # Fallback: clear status text
    if DEBUG:
        print(f"[INFO] Station {station_index+1}: MAX_WEIGHT_END received, warning cleared.")

MESSAGE_HANDLERS = {
    config.REQUEST_TARGET_WEIGHT: handle_request_target_weight,
    config.REQUEST_CALIBRATION: handle_request_calibration,
    config.REQUEST_TIME_LIMIT: handle_request_time_limit,
    config.CURRENT_WEIGHT: handle_current_weight,
    config.BEGIN_AUTO_FILL: handle_begin_auto_fill,
    config.BEGIN_SMART_FILL: handle_begin_smart_fill,
    config.FINAL_WEIGHT: handle_final_weight,
    config.FILL_TIME: handle_fill_time,
    config.MAX_WEIGHT_WARNING: handle_max_weight_warning,
    config.MAX_WEIGHT_END: handle_max_weight_end,  # <-- Register the new handler
}
