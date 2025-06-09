#!/bin/bash
# filepath: ~/start_kiosk.sh

# Wait for X to be ready
sleep 2

# Hide mouse cursor (optional, install unclutter if you want this)
unclutter &

# Launch your app (adjust the path as needed)
python3 /home/pi/sensor-relay-project/main.py