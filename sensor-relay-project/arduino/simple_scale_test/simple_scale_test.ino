#include <HX711.h>

// Pin definitions
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2

// Global variables
HX711 scale;
float scaleCalibration = 1.0; // Default calibration value

void setup() {
    Serial.begin(9600); // Start serial communication
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    // Apply the default calibration value
    scale.set_scale(scaleCalibration);
    Serial.println("Scale initialized with default calibration.");
}

void loop() {
    // Read the current weight from the scale
    long weight = scale.get_units(5); // Use 5 samples for averaging

    Serial.write(0x04);        // Send the CURRENT_WEIGHT message type
    Serial.println(weight);    // Send the weight as a string

    // delay(100); // Send weight data every 100ms
}