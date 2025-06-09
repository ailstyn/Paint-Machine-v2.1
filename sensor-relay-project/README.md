# Sensor Relay Project

This project consists of an Arduino program that reads data from an HX711 sensor and controls a relay, along with a Raspberry Pi application that tracks the data sent to and from the Arduino. The Raspberry Pi also features a Tkinter-based GUI for user interaction.

## Project Structure

```
sensor-relay-project
├── arduino
│   ├── sensor_relay.ino
├── raspberry_pi
│   ├── main.py
│   ├── gui
│   │   └── app.py
│   └── utils
│       └── serial_communication.py
├── requirements.txt
└── README.md
```

## Components

### Arduino

- **sensor_relay.ino**: This file contains the Arduino code that initializes the HX711 sensor, reads weight data, controls the relay, and manages serial communication with the Raspberry Pi.

### Raspberry Pi

- **main.py**: The main Python program that initializes serial communication with the Arduino, tracks data sent and received, and manages the overall logic of the application.

- **gui/app.py**: This file implements the Tkinter GUI for the Raspberry Pi application, providing a user interface to display data from the Arduino and allowing user interaction to control the relay.

- **utils/serial_communication.py**: Contains utility functions for handling serial communication between the Raspberry Pi and the Arduino, including functions to open the serial port, read data, and send commands.

## Requirements

To run the Python components of this project, you need to install the required dependencies. You can do this by running:

```
pip install -r requirements.txt
```

## Usage

1. Upload the Arduino code to your Arduino board.
2. Connect the Arduino to the Raspberry Pi via USB or UART.
3. Run the main Python program on the Raspberry Pi:

```
python raspberry_pi/main.py
```

4. Launch the GUI application:

```
python raspberry_pi/gui/app.py
```

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Requirements

lightdm
openbox
python3-RPI.GPIO
HX711.h
pyQt6
git
arduino-cli