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
QWidget {
    background-color: #222;
    color: #fff;
    font-family: Arial, Helvetica, sans-serif;
    font-size: 18px;
}
QLabel {
    color: #fff;
    background: transparent;
    border: none;
}
QLabel[highlight="true"] {
    background: #F6EB61;
    color: #222;
    border-radius: 8px;
    padding: 4px;
}
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
QFrame {
    background: transparent;
    border: 2px solid #ccc;
    border-radius: 14px;
}
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
"""