#!/bin/bash
while true; do
    timeout 600s python3 /home/chris/Paint-Machine-v2.1/sensor-relay-project/raspberry_pi/main.py
    echo "main.py exited or froze, restarting in 2 seconds..."
    sleep 2
done