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