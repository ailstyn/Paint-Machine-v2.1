#!/bin/bash
# filepath: ~/start_kiosk.sh

# Wait for X to be ready
sleep 2

# Hide mouse cursor (optional, install unclutter if you want this)
unclutter &

# Launch your app (adjust the path as needed)
python3 /home/chris/Paint-Machine-v2.1/sensor-relay-project/raspberry_pi/main.py