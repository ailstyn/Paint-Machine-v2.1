#!/bin/bash
echo "[DEBUG] start_kiosk.sh: pwd=$(pwd)"
echo "[DEBUG] start_kiosk.sh: whoami=$(whoami)"
echo "[DEBUG] start_kiosk.sh: groups=$(groups)"
env > /tmp/env_kiosk.txt
# filepath: ~/start_kiosk.sh

# Wait for X to be ready
sleep 2

# Hide mouse cursor (optional, install unclutter if you want this)
unclutter &

# Check for internet connection
if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
	echo "Internet connection detected. Running update.sh..."
	cd /home/chris/Paint-Machine-v2.1/sensor-relay-project
	./update.sh
	cd raspberry_pi
	python3 main.py
else
	echo "No internet connection. Skipping update."
	cd /home/chris/Paint-Machine-v2.1/sensor-relay-project/raspberry_pi
	python3 main.py
fi