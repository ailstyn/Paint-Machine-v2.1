#!/bin/bash
echo "[DEBUG] update.sh: pwd=$(pwd)"
echo "[DEBUG] update.sh: whoami=$(whoami)"
echo "[DEBUG] update.sh: groups=$(groups)"
echo "[DEBUG] update.sh: lsusb="
lsusb
echo "[DEBUG] update.sh: ls -l /dev/ttyACM* /dev/ttyUSB*"
ls -l /dev/ttyACM* /dev/ttyUSB* 2>&1 || true
env > /tmp/env_update.txt
# filepath: /sensor-relay-project/update_and_flash.sh

set -e

# 1. Update repo
echo "Updating repository..."
sudo git pull

# 2. Compile the Arduino sketch
SKETCH_PATH="arduino/scale_controller/scale_controller.ino"
FQBN="arduino:avr:leonardo"  # Change this if you use a different board type

echo "Compiling $SKETCH_PATH ..."
arduino-cli compile --fqbn $FQBN $SKETCH_PATH

# 3. Find connected Arduinos
echo "Detecting connected Arduinos..."
PORTS=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true)

if [ -z "$PORTS" ]; then
    echo "No Arduinos detected."
    exit 1
fi

# 4. Upload to each Arduino
for PORT in $PORTS; do
    echo "Uploading to $PORT ..."
    arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH_PATH
done

echo "Update and upload complete."