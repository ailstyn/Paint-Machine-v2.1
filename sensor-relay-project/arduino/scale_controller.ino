#include <HX711.h>

// Pin definitions
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2
#define RELAY_PIN 4
#define BUTTON_PIN 5

// Global variables
HX711 scale;
float scaleCalibration = 1.0; // Default calibration value
float calibWeight = 50.0;     // Calibration weight in grams

void setup() {
    Serial.begin(9600); // Start serial communication
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP); // Use INPUT_PULLUP for a momentary button
    digitalWrite(RELAY_PIN, LOW); // Ensure relay is LOW on startup
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    // Request calibration value from Raspberry Pi
    Serial.println("REQUEST_CALIBRATION");

    // Wait for the calibration value from the Raspberry Pi
    while (true) {
        if (Serial.available()) {
            String receivedData = Serial.readStringUntil('\n'); // Read the incoming data
            if (receivedData.startsWith("cal_")) { // Check if the data starts with "cal_"
                scaleCalibration = receivedData.substring(4).toFloat(); // Extract the calibration value
                scale.set_scale(scaleCalibration); // Apply the calibration value
                break; // Exit the loop once the calibration value is received
            }
        }
    }

    // Print the received calibration value for debugging
    Serial.print("Calibration value received and applied: ");
    Serial.println(scaleCalibration);
}

void loop() {
    // Check for button press
    if (digitalRead(BUTTON_PIN) == LOW) { // Button pressed (LOW due to pull-up)
        fill();
    }

    // Check for incoming serial messages
    if (Serial.available()) {
        String receivedData = Serial.readStringUntil('\n'); // Read the incoming data
        if (receivedData == "RESET_CALIBRATION") {
            recalibrate(); // Trigger recalibration
        }
    }

    // Read and print weight from HX711
    long weight = scale.get_units(10); // Apply calibration automatically
    Serial.println(weight);
    delay(1000);
}

// Function to handle the fill process
void fill() {
    // Request target weight from Raspberry Pi
    Serial.println("REQUEST_TARGET_WEIGHT");

    String receivedData = "";
    float targetWeight = 0.0;
    while (true) {
        if (Serial.available()) {
            receivedData = Serial.readStringUntil('\n'); // Read the incoming data
            if (receivedData.startsWith("tw_")) { // Check if the data starts with "tw_"
                targetWeight = receivedData.substring(3).toFloat(); // Extract the target weight
                break; // Exit the loop once the target weight is received
            }
        }
    }

    // Start filling process
    Serial.print("Target Weight Received: ");
    Serial.println(targetWeight);

    digitalWrite(RELAY_PIN, HIGH); // Turn relay ON
    while (scale.get_units(10) < targetWeight) {
        // Keep filling until the target weight is reached
        delay(100); // Small delay to avoid overwhelming the scale
    }
    digitalWrite(RELAY_PIN, LOW); // Turn relay OFF
    Serial.println("Filling Complete");
}

// Function to handle recalibration
void recalibrate() {
    Serial.println("Starting recalibration...");

    // Continuously send current scale readings to the Raspberry Pi
    while (true) {
        long weight = scale.get_units(10);
        Serial.print("Current Weight: ");
        Serial.println(weight);

        // Check for button press to start the first step of recalibration
        if (digitalRead(BUTTON_PIN) == LOW) {
            delay(200); // Debounce delay
            scale.set_scale(); // Reset the scale
            scale.tare();      // Tare the scale
            Serial.println("Scale reset and tared. Place calibration weight.");
            break;
        }
        delay(500); // Delay to avoid overwhelming the serial output
    }

    // Wait for the second button press to finalize calibration
    while (true) {
        long weight = scale.get_units(10);
        Serial.print("Current Weight: ");
        Serial.println(weight);

        if (digitalRead(BUTTON_PIN) == LOW) {
            delay(200); // Debounce delay
            float rawUnits = scale.get_units(10); // Get the raw units
            scaleCalibration = rawUnits / calibWeight; // Calculate the new calibration factor
            scale.set_scale(scaleCalibration); // Apply the new calibration factor
            Serial.print("New calibration factor applied: ");
            Serial.println(scaleCalibration);
            break;
        }
        delay(500); // Delay to avoid overwhelming the serial output
    }

    Serial.println("Recalibration complete.");
}