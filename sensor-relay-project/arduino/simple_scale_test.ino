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
    long weight = scale.get_units(10); // Use 10 samples for averaging
    Serial.print("Weight: ");
    Serial.println(weight);

    delay(1000); // Send weight data every second
}