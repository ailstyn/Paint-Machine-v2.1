# Sensor Relay Project

This project consists of an Arduino program that reads data from an HX711 sensor and controls a relay, along with a Raspberry Pi application that communicates with the Arduino and provides a PyQt6-based GUI for user interaction.

## Project Structure

```
sensor-relay-project
├── arduino
│   ├── scale_controller
│   │   └── scale_controller.ino
├── raspberry_pi
│   ├── main.py
│   ├── gui
│   │   ├── qt_gui.py
│   │   └── languages.py
│   └── utils
│       └── serial_communication.py
├── requirements.txt
└── README.md
```

## Components

### Arduino

- **scale_controller.ino**: Arduino code that initializes the HX711 sensor, reads weight data, controls the relay, manages calibration, and communicates with the Raspberry Pi via serial.

### Raspberry Pi

- **main.py**: Main Python program that manages serial communication with the Arduino, tracks data, and controls the overall application logic.
- **gui/qt_gui.py**: Implements the PyQt6 GUI for the Raspberry Pi application, providing a modern user interface to display data from the Arduino and allow user interaction.
- **gui/languages.py**: Contains language dictionaries for localization (English and Spanish).
- **utils/serial_communication.py**: Utility functions for handling serial communication between the Raspberry Pi and the Arduino.

## Requirements

To run the Python components of this project, install the required dependencies:

```
pip install -r requirements.txt
```

**System/Package Requirements:**
- lightdm
- openbox
- python3-RPI.GPIO
- HX711.h (Arduino library)
- pyQt6
- git
- arduino-cli

## Usage

1. Upload the Arduino code (`scale_controller.ino`) to your Arduino board.
2. Connect the Arduino to the Raspberry Pi via USB or UART.
3. On the Raspberry Pi, run the main Python program:
    ```
    python raspberry_pi/main.py
    ```
4. The PyQt6 GUI will launch automatically, or you can run it directly:
    ```
    python raspberry_pi/gui/qt_gui.py
    ```

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## Icon Credits

- [Diameter icons created by Vectorslab - Flaticon](https://www.flaticon.com/free-icons/diameter)
- [Dumbell icons created by Vitaly Gorbachev - Flaticon](https://www.flaticon.com/free-icons/dumbell)
- [Color wheel icons created by Hasymi - Flaticon](https://www.flaticon.com/free-icons/color-wheel)
- [Global icons created by srip - Flaticon](https://www.flaticon.com/free-icons/global)
- [Ruler icons created by Good Ware - Flaticon](https://www.flaticon.com/free-icons/ruler)