"""
Experimental startup sequence logic for Paint Machine
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QDialog
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt
import time
from startup import step_clear_all_scales
import logging


class StartupWizardDialog(QDialog):
    step_completed = pyqtSignal(dict)

    def __init__(self, parent=None, num_stations=4, bottle_ranges=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(1024, 600)
        self.num_stations = num_stations

        # State
        self.station_enabled = [True] * num_stations
        self.station_connected = [True] * num_stations
        self.weight_texts = ["--"] * num_stations
        self.station_weights = [0.0] * num_stations
        self.selection_indices = []
        self.selection_index = 0
        self.active_prompt = None

        # Layouts
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(24, 16, 24, 16)
        self.main_layout.setSpacing(8)

        self.main_label = QLabel()
        self.main_label.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        self.main_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_palette = self.main_label.palette()
        main_palette.setColor(QPalette.ColorRole.WindowText, QColor("#eee"))
        self.main_label.setPalette(main_palette)
        self.main_layout.addWidget(self.main_label)

        self.info_label = QLabel()
        self.info_label.setFont(QFont("Arial", 22))
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.info_label.setFixedHeight(200)
        self.info_label.setWordWrap(True)
        info_palette = self.info_label.palette()
        info_palette.setColor(QPalette.ColorRole.WindowText, QColor("#eee"))
        self.info_label.setPalette(info_palette)
        self.main_layout.addWidget(self.info_label)

        self.stations_layout = QHBoxLayout()
        self.stations_layout.setSpacing(10)
        self.station_boxes = []
        self.station_frames = []
        for i in range(self.num_stations):
            box = StationBoxWidget(
                station_index=i,
                name=f"Station {i+1}",
                color=STATION_COLORS[i],
                connected=True,
                enabled=True,
                weight_text="--",
                parent=self
            )
            box.setMinimumWidth(216)
            box.setMinimumHeight(110)
            box.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
            self.station_boxes.append(box)
            frame = QFrame()
            frame.setObjectName(f"stationFrame_{i}")
            frame.setFrameShape(QFrame.Shape.StyledPanel)
            frame.setLineWidth(0)
            frame.setLayout(QVBoxLayout())
            frame.layout().setContentsMargins(1, 1, 1, 1)
            frame.layout().setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame.layout().addWidget(box)
            frame.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)
            frame.paintEvent = lambda event, f=frame: frame_paintEvent(f, event)
            self.station_frames.append(frame)
            self.stations_layout.addWidget(frame)
        self.main_layout.addLayout(self.stations_layout, stretch=2)
        self.main_layout.addStretch(1)

        self.accept_label = OutlinedLabel(
            "CONTINUE",
            font_size=36,
            bold=True,
            color="#fff",
            bg_color=None,
            border_radius=16,
            padding=8
        )
        self.accept_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.accept_label.setMinimumHeight(50)
        self.accept_label.setFixedWidth(360)
        self.accept_label.set_highlight(False)
        self.main_layout.addWidget(self.accept_label, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.back_label = OutlinedLabel(
            "BACK",
            font_size=36,
            bold=True,
            color="#fff",
            bg_color=None,
            border_radius=16,
            padding=8
        )
        self.back_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.back_label.setMinimumHeight(50)
        self.back_label.setFixedWidth(360)
        self.back_label.set_highlight(False)
        self.main_layout.addWidget(self.back_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.back_label.hide()  # Only show on steps > 0

        self.button_column = ButtonColumnWidget(parent=self)
        h_layout = QHBoxLayout()
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        h_layout.addLayout(self.main_layout, stretch=10)
        h_layout.addWidget(self.button_column, stretch=0)
        self.setLayout(h_layout)

        # No direct step logic here; main loop controls which prompt to show

    def show_station_verification(self):
        self.active_prompt = "station_verification"
        self.main_label.setText("Verify Stations")
        self.info_label.setText("Enable or disable stations as needed. Use UP/DOWN to select, SELECT to toggle, CONTINUE to proceed.")
        self.selection_indices = [i for i, c in enumerate(self.station_connected) if c] + ["accept"]
        self.selection_index = len(self.selection_indices) - 1
        self.update_highlight()
        self.back_label.hide()

    def show_empty_scale_prompt(self):
        self.active_prompt = "empty_scale"
        self.main_label.setText("Place Empty Scale")
        self.info_label.setText("Remove all bottles and objects from the scale. Press CONTINUE or BACK.")
        self.selection_indices = ["back", "accept"]
        self.selection_index = 1
        self.update_highlight()
        self.back_label.show()

    def show_full_bottle_prompt(self, full_ranges):
        self.active_prompt = "full_bottle"
        self.full_bottle_ranges = full_ranges
        self.main_label.setText("Place Full Bottle")
        info_lines = ["Place a full bottle on each enabled station. Press CONTINUE or BACK."]
        for name, rng in full_ranges.items():
            info_lines.append(f"{name}: {rng[0]}g - {rng[1]}g")
        self.info_label.setText("\n".join(info_lines))
        self.selection_indices = ["back", "accept"]
        self.selection_index = 1
        self.update_highlight()
        self.back_label.show()

    def show_empty_bottle_prompt(self, empty_range=(0, 0)):
        self.active_prompt = "empty_bottle"
        self.empty_bottle_range = empty_range
        self.main_label.setText("Place Empty Bottle")
        self.info_label.setText("Replace the full bottle with an empty bottle on each enabled station. Press CONTINUE or BACK.")
        self.selection_indices = ["back", "accept"]
        self.selection_index = 1
        self.update_highlight()
        self.back_label.show()

    def activate_selected(self):
        selected = self.selection_indices[self.selection_index]
        print(f"[DEBUG] activate_selected called, active_prompt={self.active_prompt}, selection={selected}")
        if selected == "accept":
            self.complete_step(self.active_prompt)
        elif selected == "back":
            self.step_completed.emit({"step": self.active_prompt, "action": "backup"})
        elif isinstance(selected, int):
            self.toggle_station(selected)

    def complete_step(self, step_name, extra_data=None):
        info = {"step": step_name}
        if extra_data:
            info.update(extra_data)
        self.step_completed.emit(info)

# Example step functions

def step_load_serials_and_ranges(context):
    print("Step: Load serials, bottle sizes, and ranges")
    # Simulate loading config, serials, bottle sizes, ranges
    context['station_serials'] = ['SN001', 'SN002', 'SN003', 'SN004']
    context['bottle_sizes'] = {'A': (500, 50, 3000)}
    context['bottle_ranges'] = {'A': {'full': (475, 525), 'empty': (25, 75)}}
    return 'completed'


def step_connect_arduinos(context):
    print("Step: Connect and initialize Arduinos")
    # Simulate connecting
    context['station_connected'] = [True, True, True, True]
    context['arduinos'] = ['Arduino1', 'Arduino2', 'Arduino3', 'Arduino4']
    return 'completed'


def step_check_estop(context):
    print("Step: Check E-STOP state")
    # Simulate E-STOP released
    context['estop_released'] = True
    return 'completed'


def step_station_verification(context):
    wizard = context['wizard']
    app = context['app']
    step_result = {}
    wizard.show_station_verification()
    wizard.show()
    while not step_result or step_result.get("step") != "station_verification":
        app.processEvents()
        time.sleep(0.01)
    # Optionally update context with results
    context['station_enabled'] = step_result.get('enabled', [])
    return 'completed'


def step_tare_scales(context):
    print("Step: Send TARE_SCALE to Arduinos")
    # Simulate sending TARE
    context['tare_sent'] = True
    return 'completed'


def step_filling_mode_selection(context):
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
                print(f"[DEBUG] Exception in filling_mode_callback: {e}")
            selection_dialog.accept()
        selection_dialog.on_select_callback = on_select

        timeout_seconds = 5.0
        start_time = time.time()
        while selection_dialog.isVisible():
            app.processEvents()
            time.sleep(0.01)
            if time.time() - start_time > timeout_seconds:
                if filling_mode_selected is None:
                    filling_mode_selected = "AUTO"
                    filling_mode_callback("AUTO")
                    selection_dialog.accept()
        print("[DEBUG] SelectionDialog no longer visible.")
    except Exception as e:
        print(f"[DEBUG] Exception during filling mode dialog: {e}")
        logging.error(f"Exception during filling mode dialog: {e}")

    app.active_dialog = wizard
    context['filling_mode'] = filling_mode_selected

    # Handle MANUAL mode early exit
    if filling_mode_selected == "MANUAL":
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

    return 'completed'


def step_full_bottle(context):
    print("Step: Calibration - Place full bottles")
    context['selected_bottle_id'] = 'A'
    context['target_weight'] = 500
    context['time_limit'] = 3000
    return 'completed'


def step_empty_bottle(context):
    print("Step: Calibration - Place empty bottles")
    context['empty_bottle_ok'] = True
    return 'completed'


def step_clear_all_scales(context):
    wizard = context['wizard']
    app = context['app']
    NUM_STATIONS = context['NUM_STATIONS']
    station_enabled = context['station_enabled']
    station_connected = context['station_connected']
    arduinos = context['arduinos']
    config = context['config']
    step_result = {}

    while True:
        wizard.show_empty_scale_prompt()
        wizard.show()
        while not step_result or step_result.get("step") != "empty_scale":
            app.processEvents()
            time.sleep(0.01)

        scale_values = [wizard.get_weight(i) for i in range(NUM_STATIONS) if station_enabled[i] and station_connected[i]]
        if any(w > 20 for w in scale_values):
            options = [("CONFIRM", "CONFIRM"), ("BACK", "BACK")]
            selection_dialog = context['SelectionDialog'](options=options, title="Confirm All Scales Are Clear")
            selection_dialog.selected_index = 1
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
            if user_choice == "CONFIRM":
                break
            else:
                step_result.clear()
                continue
        else:
            break

    # Send TARE_SCALE to each enabled and connected Arduino
    for i, arduino in enumerate(arduinos):
        if arduino and station_enabled[i] and station_connected[i]:
            try:
                arduino.write(config.TARE_SCALE)
                arduino.flush()
            except Exception as e:
                context['logging'].error(f"Error sending TARE_SCALE to station {i+1}: {e}")

    return 'completed'


def step_full_bottle_check(context):
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
    config_file = context['config_file']
    DEBUG = context.get('DEBUG', False)

    full_ranges = {name: bottle_ranges[name]["full"] for name in bottle_ranges}
    wizard.show_full_bottle_prompt(full_ranges)
    wizard.show()
    step_result = {}

    selected_bottle_id = None
    while True:
        # Wait for user to press CONTINUE
        while not step_result or step_result.get("step") != "full_bottle":
            app.processEvents()
            time.sleep(0.01)

        # After CONTINUE is pressed, check all active stations
        active_weights = [
            wizard.get_weight(i)
            for i in range(NUM_STATIONS)
            if station_enabled[i] and station_connected[i]
        ]

        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        found = False
        for bottle_id, rng in full_ranges.items():
            if all(in_range(w, rng) for w in active_weights):
                selected_bottle_id = bottle_id
                found = True
                break

        if not found:
            dlg = InfoDialog(
                app.tr("Error") if hasattr(app, 'tr') else "Error",
                app.tr("All bottles must be within the same size range.") if hasattr(app, 'tr') else "All bottles must be within the same size range.",
                wizard
            )
            ping_buzzer_invalid()
            dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            dlg.show()
            QTimer.singleShot(2000, dlg.accept)
            step_result.clear()  # Wait for user to try again
            continue
        else:
            break  # Proceed to next step

    # Set target_weight and time_limit based on selected bottle
    target_weight = None
    time_limit = None
    if selected_bottle_id:
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
                try:
                    target_weight = float(parts[0])
                    time_limit = int(parts[2])
                    if DEBUG:
                        print(f"[DEBUG] Set target_weight to {target_weight} and time_limit to {time_limit} for bottle {selected_bottle_id}")
                except Exception as e:
                    print(f"[DEBUG] Error parsing bottle config for {selected_bottle_id}: {e}")

    # Store results in context for later steps
    context['selected_bottle_id'] = selected_bottle_id
    context['target_weight'] = target_weight
    context['time_limit'] = time_limit

    # Now show empty bottle prompt (if needed, or return to let next step handle it)
    wizard.show_empty_bottle_prompt()
    wizard.show()

    return 'completed'

def step_empty_bottle_check(context):
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
    wizard.show()
    step_result = {}

    while True:
        step_result.clear()
        while not step_result or step_result.get("step") != "empty_bottle":
            app.processEvents()
            time.sleep(0.01)

        active_weights = [
            wizard.get_weight(i)
            for i in range(NUM_STATIONS)
            if station_enabled[i] and station_connected[i]
        ]

        def in_range(w, rng):
            return rng[0] <= w <= rng[1]

        if not all(in_range(w, empty_range) for w in active_weights):
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
        else:
            bottle_config_line = None
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
                    print(f"[DEBUG] Error parsing bottle config for {selected_bottle_id}: {e}")
            if after_startup:
                after_startup()
            wizard.finish_wizard()
            app.active_dialog = app
            break
    return 'completed'

# List of step functions in order
startup_steps = [
    step_load_serials_and_ranges,
    step_connect_arduinos,
    step_check_estop,
    step_station_verification,
    step_clear_all_scales,
    step_filling_mode_selection,
    step_full_bottle,
    step_empty_bottle,
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
        sys.exit()  # Exits the script early