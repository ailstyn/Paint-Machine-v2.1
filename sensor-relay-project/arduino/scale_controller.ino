#include <HX711.h>

// Pin definitions
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2
#define RELAY_PIN 4
#define BUTTON_PIN 5
#define STATUS_LED 13 // Built-in LED on pin 13 for Arduino Leonardo

// Global variables
HX711 scale;
float scaleCalibration = 1.0; // Default calibration value
float calibWeight = 50.0;     // Calibration weight in grams

void setup() {
    Serial.begin(9600); // Start serial communication
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(BUTTON_PIN, INPUT_PULLUP); // Use INPUT_PULLUP for a momentary button
    pinMode(STATUS_LED, OUTPUT);      // Set the status LED pin as output
    digitalWrite(RELAY_PIN, LOW);     // Ensure relay is LOW on startup
    digitalWrite(STATUS_LED, LOW);    // Turn off the status LED initially
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    // Request calibration value from Raspberry Pi
    Serial.println("REQUEST_CALIBRATION");

    // Wait for the calibration value from the Raspberry Pi
    while (true) {
        if (Serial.available() > 0) {
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
    // Blink the status LED to indicate the loop is running
    digitalWrite(STATUS_LED, HIGH); // Turn the LED on
    delay(500);                     // Wait for 500ms
    digitalWrite(STATUS_LED, LOW);  // Turn the LED off
    delay(500);                     // Wait for 500ms

    // Check for button press
    if (digitalRead(BUTTON_PIN) == LOW) { // Button pressed (LOW due to pull-up)
        fill();
    }

    // Check for incoming serial messages
    if (Serial.available() > 0) {
        String receivedData = Serial.readStringUntil('\n'); // Read the incoming data

        // Handle recalibration request
        if (receivedData == "RESET_CALIBRATION") {
            recalibrate(); // Trigger recalibration
        }

        // Handle connection test
        else if (receivedData == "CONNECTION_TEST") {
            Serial.println("ARDUINO_ONLINE"); // Respond to connection test
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

    // Wait to receive the target weight from the Raspberry Pi
    while (true) {
        if (Serial.available()) {
            receivedData = Serial.readStringUntil('\n'); // Read the incoming data
            if (receivedData.startsWith("tw_")) { // Check if the data starts with "tw_"
                targetWeight = receivedData.substring(3).toFloat(); // Extract the target weight
                break; // Exit the loop once the target weight is received
            }
        }
    }

    // Request time limit from Raspberry Pi
    Serial.println("REQUEST_TIME_LIMIT");

    unsigned long timeLimit = 0;

    // Wait to receive the time limit from the Raspberry Pi
    while (true) {
        if (Serial.available()) {
            receivedData = Serial.readStringUntil('\n'); // Read the incoming data
            if (receivedData.startsWith("tl_")) { // Check if the data starts with "tl_"
                timeLimit = receivedData.substring(3).toInt(); // Extract the time limit
                break; // Exit the loop once the time limit is received
            }
        }
    }

    // Start the validation process
    Serial.print("Target Weight Received: ");
    Serial.println(targetWeight);
    Serial.print("Time Limit Received: ");
    Serial.println(timeLimit);

    // Check the current weight on the scale
    long currentWeight = scale.get_units(10); // Get the current weight
    Serial.print("Current Weight: ");
    Serial.println(currentWeight);

    // If the current weight is greater than 20% of the target weight, abort the fill process
    if (currentWeight > 0.2 * targetWeight) {
        Serial.println("ERROR: CLEAR SCALE"); // Send error message to the Raspberry Pi
        return; // Exit the function without starting the fill process
    }

    // Start filling process
    unsigned long startTime = millis(); // Record the start time
    digitalWrite(RELAY_PIN, HIGH);      // Turn relay ON

    while (scale.get_units(5) < targetWeight) { // Use 5 samples for faster response
        unsigned long currentTime = millis(); // Get the current time
        unsigned long elapsedTime = currentTime - startTime; // Calculate elapsed time
        timeLimit -= elapsedTime; // Subtract elapsed time from the time limit
        startTime = currentTime;  // Update the start time for the next iteration

        // Check if the time limit has been exceeded
        if (timeLimit <= 0) {
            Serial.println("ERROR: TIME LIMIT EXCEEDED"); // Send error message to the Raspberry Pi
            digitalWrite(RELAY_PIN, LOW); // Turn relay OFF
            return; // Exit the function
        }

        delay(50); // Small delay to allow the loop to run faster
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