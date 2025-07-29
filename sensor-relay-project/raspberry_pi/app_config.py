DEBUG = True

NUM_STATIONS = 4
target_weight = 500.0
time_limit = 3000

config_file = "config.txt"

# Log directories
LOG_DIR = "logs"
ERROR_LOG_DIR = "logs/errors"
STATS_LOG_DIR = "logs/stats"

from datetime import datetime
SESSION_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

# Example log file paths (use these in your logging setup)
ERROR_LOG_FILE = f"{ERROR_LOG_DIR}/error_log_{datetime.now().strftime('%Y-%m-%d')}.txt"
STATS_LOG_FILE = f"{STATS_LOG_DIR}/material_log_{datetime.now().strftime('%Y-%m-%d')}.txt"

# Protocol bytes
REQUEST_TARGET_WEIGHT = b'\x01'
REQUEST_CALIBRATION = b'\x02'
REQUEST_TIME_LIMIT = b'\x03'
CURRENT_WEIGHT = b'\x04'
RESET_CALIBRATION = b'\x05'
TARE_SCALE = b'\x09'
RELAY_DEACTIVATED = b'\xFA'
TARGET_WEIGHT = b'\x08'
VERBOSE_DEBUG = b'\xFE'
BEGIN_AUTO_FILL = b'\x10'
SET_MANUAL_FILL = b'\x16'
BEGIN_SMART_FILL = b'\x17'
CALIBRATION_STEP_DONE = b'\x12'
CALIBRATION_CONTINUE = b'\x13'
CALIBRATION_WEIGHT = b'\x14'
E_STOP_ACTIVATED = b'\xEE'
FILL_TIME = b'\x15'
FINAL_WEIGHT = b'\x11'
GET_ID = b'\xA0'
STOP = b'\xFD'
CONFIRM_ID = b'\xA1'
RESET_HANDSHAKE = b'\xB0'
BUTTON_ERROR = b'\xE0'
MAX_WEIGHT_WARNING = b'\xE1'
MAX_WEIGHT_END = b'\xE2'
EXIT_MANUAL_END = b'\x22'
MANUAL_FILL_START = b'\x20'

# GPIO pins
UP_BUTTON_PIN = 5
DOWN_BUTTON_PIN = 6
SELECT_BUTTON_PIN = 16
E_STOP_PIN = 23
BUZZER_PIN = 26
RELAY_POWER_PIN = 17

arduino_ports = [
    '/dev/ttyACM0',
    '/dev/ttyACM1',
    '/dev/ttyACM2',
    '/dev/ttyACM3'
]

# Unified Qt Stylesheet for the GUI
QT_STYLESHEET = """
/* Unified Qt Stylesheet for Paint Machine GUI */

QWidget {
    background-color: #222;
    color: #fff;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 18px;
}

/* Generic label styles */
QLabel {
    color: #fff;
    background: transparent;
    border: none;
}

/* Highlighted labels (used for selection) */
QLabel[highlight="true"] {
    background: #F6EB61;
    color: #222;
    border-radius: 8px;
    padding: 4px;
}

/* Large weight label for RelayControlApp */
QLabel#weightLabel {
    color: #0f0;
    font-size: 64px;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 4px;
}

/* Small weight label for StartupWizardDialog/StationBoxWidget */
QLabel#smallweightLabel {
    color: #0f0;
    font-size: 32px;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 2px;
}

/* Offline label for RelayControlApp */
QLabel#offlineLabel {
    color: #FF2222;
    font-size: 54px;
    font-weight: bold;
    background: transparent;
    border: none;
    padding: 4px;
}

/* Accept/Continue label */
QLabel#acceptLabel {
    color: #fff;
    background: transparent;
    border-radius: 12px;
    padding: 12px 32px;
    margin-top: 18px;
}
QLabel#acceptLabel[highlight="true"] {
    color: #222;
    background: #F6EB61;
    border-radius: 12px;
    padding: 12px 32px;
    margin-top: 18px;
}
QLabel#acceptLabel[highlight="false"] {
    color: #fff;
    background: transparent;
    border-radius: 12px;
    padding: 12px 32px;
    margin-top: 18px;
}

/* Status label */
QLabel#statusLabel {
    color: #fff;
    font-size: 20px;
}

/* Arrow labels for SetTargetWeightDialog */
QLabel#arrowLabel {
    color: #fff;
    font-size: 28px;
    background: transparent;
    border: none;
    padding: 4px 0;
    transition: color 0.2s;
}

/* Digit labels for SetTargetWeightDialog */
QLabel#digitLabel {
    color: #fff;
    font-size: 48px;
    background: transparent;
    border-radius: 8px;
    border: 2px solid transparent;
    padding: 4px 0;
    min-width: 48px;
    transition: color 0.2s, border-color 0.2s;
}

/* Highlighted digit label */
QLabel#digitLabel[highlight="true"] {
    color: #F6EB61;
    border: 2px solid #F6EB61;
    background: #222;
}

/* OutlinedLabel (station name, etc.) */
OutlinedLabel {
    background: transparent;
    padding: 4px;
}

/* StationBoxWidget connected/enabled labels */
QLabel.stationStatusLabel {
    border-radius: 8px;
    border: none;
    padding: 4px;
    color: #fff;
}

/* InfoDialog title/value labels */
QLabel#titleLabel {
    color: #fff;
    font-size: 32px;
    font-weight: bold;
    padding: 12px;
}
QLabel#valueLabel {
    color: #fff;
    font-size: 48px;
    font-weight: bold;
    padding: 12px;
}

/* Frame styles */
QFrame {
    background: transparent;
    border: 2px solid #ccc;
    border-radius: 14px;
}
QFrame[highlight="true"] {
    background: #F6EB61;
    border-radius: 14px;
}
QFrame[highlight="false"] {
    background: transparent;
    border-radius: 14px;
}

/* Dialog styles */
QDialog {
    background-color: #222;
    border: 6px solid #F6EB61;
    border-radius: 24px;
}

/* Station color classes */
.station-red    { background: #CB1212; color: #fff; }
.station-blue   { background: #2E4BA8; color: #fff; }
.station-green  { background: #3f922e; color: #fff; }
.station-yellow { background: #EDE021; color: #222; }

/* Button column styles */
QWidget#buttonColumn {
    background: transparent;
    padding: 12px 0px;
    min-width: 56px;
    max-width: 64px;
}
QLabel.buttonColumnLabel {
    font-size: 32px;
    color: #fff;
    padding: 8px 0px;
    margin-bottom: 18px;
    border-radius: 12px;
    background: #333;
}

/* QPushButton styles */
QPushButton, QDialog QPushButton {
    background-color: #444;
    color: #fff;
    border-radius: 12px;
    padding: 8px 24px;
    font-size: 20px;
    font-weight: bold;
}
QPushButton:hover, QDialog QPushButton:hover {
    background-color: #F6EB61;
    color: #222;
}

/* Menu label style */
QLabel#menuLabel {
    font-size: 28px;
    padding: 12px 0;
}

OutlinedLabel[highlight="true"], QLabel[highlight="true"] {
    border: 4px solid #F6EB61;
    border-radius: 16px;
    background: transparent;
    font-size: 24px;
}
OutlinedLabel[highlight="false"], QLabel[highlight="false"] {
    border: 4px solid transparent;
    border-radius: 16px;
    background: transparent;
    font-size: 24px;
}

/* Overlay styles */
OverlayWidget {
    background: rgba(0,0,0,180);
    border-radius: 32px;
}
QLabel#overlayLabel {
    color: #fff;
    font-size: 64px;
    font-weight: bold;
    background: transparent;
}
"""