#!/bin/bash
env > /tmp/env_update.txt
# filepath: /sensor-relay-project/update_and_flash.sh

set -e

# 1. Update repo
echo "Updating repository..."
sudo git pull

# 2. Check if scale_controller.ino changed in last pull
SKETCH_PATH="arduino/scale_controller/scale_controller.ino"
FQBN="arduino:avr:leonardo"  # Change this if you use a different board type

if ! git diff --name-only HEAD@{1} HEAD | grep -q "$SKETCH_PATH"; then
    echo "No changes to $SKETCH_PATH detected. Skipping Arduino compile/upload."
    exit 0
fi

# 3. Compile the Arduino sketch
echo "Compiling $SKETCH_PATH ..."
arduino-cli compile --fqbn $FQBN $SKETCH_PATH

# 4. Find connected Arduinos
echo "Detecting connected Arduinos..."
PORTS=$(ls /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || true)

if [ -z "$PORTS" ]; then
    echo "No Arduinos detected."
    exit 1
fi

# 5. Upload to each Arduino
for PORT in $PORTS; do
    echo "Uploading to $PORT ..."
    arduino-cli upload -p $PORT --fqbn $FQBN $SKETCH_PATH
done

echo "Update and upload complete."