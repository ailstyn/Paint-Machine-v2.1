#include <HX711.h>

const int LOADCELL_DOUT_PIN = 3;
const int LOADCELL_SCK_PIN = 2;
const int RELAY_PIN = 4;
const int BUTTON_PIN = 5; // Pin for the momentary button

HX711 scale;
float targetWeight = 0.0; // Variable to store the target weight

void setup() {
    Serial.begin(9600);
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP); // Use INPUT_PULLUP for a momentary button
    digitalWrite(RELAY_PIN, LOW); // Ensure relay is LOW on startup
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
}

void loop() {
    // Check for button press
    if (digitalRead(BUTTON_PIN) == LOW) { // Button pressed (LOW due to pull-up)
        fill();
    }

    // Read and print weight from HX711
    long weight = scale.get_units(10);
    Serial.println(weight);
    delay(1000);
}

// Function to handle the fill process
void fill() {
    // Request target weight from Raspberry Pi
    Serial.println("REQUEST_TARGET_WEIGHT");
    while (!Serial.available()) {
        // Wait for response from Raspberry Pi
    }
    targetWeight = Serial.readStringUntil('\n').toFloat();

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