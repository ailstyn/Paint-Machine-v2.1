#include <HX711.h>

// Pin definitions
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2
#define RELAY_PIN 21
#define BUTTON_PIN 10
#define LED_PIN 16

// Byte-based protocol for communication
#define REQUEST_TARGET_WEIGHT 0x01
#define TARGET_WEIGHT 0x08
#define REQUEST_CALIBRATION 0x02
#define REQUEST_TIME_LIMIT 0x03
#define CURRENT_WEIGHT 0x04
#define RESET_CALIBRATION 0x05
#define PLACE_CALIBRATION_WEIGHT 0x06
#define CALIBRATION_COMPLETE 0x07
#define TARE_SCALE 0x09
#define RELAY_DEACTIVATED 0x0A

// Global variables
HX711 scale;
float scaleCalibration = 427.530059; // Default calibration value
float calibWeight = 61.0;     // Calibration weight in grams

void setup() {
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, HIGH);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    Serial.begin(9600);
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);

    // Wait for "PI READY" message
    while (true) {
        if (Serial.available() > 0) {
            byte msg = Serial.read();
            if (msg == 'P') {
                break;
            }
        }
    }

    // Now Pi is ready, repeatedly request calibration until received
    while (true) {
        Serial.write(REQUEST_CALIBRATION); // Request calibration
        unsigned long start = millis();
        bool received = false;
        while (millis() - start < 500) { // Wait up to 500ms for a response
            if (Serial.available() > 0) {
                byte messageType = Serial.read(); // Read the message type
                if (messageType == REQUEST_CALIBRATION) {
                    String receivedData = Serial.readStringUntil('\n'); // Read the calibration value
                    scaleCalibration = receivedData.toFloat(); // Convert to float
                    scale.set_scale(scaleCalibration); // Apply the calibration value
                    received = true;
                    break; // Exit the inner wait loop
                }
            }
        }
        if (received) break; // Exit the outer request loop if calibration received
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
    if (Serial.available() > 0) {
        byte messageType = Serial.read(); // Read the message type

        // Handle tare command
        if (messageType == TARE_SCALE) {
            Serial.println("Taring scale...");
            scale.tare();  // Tare the scale
            Serial.println("Scale tared.");
        }

        // Handle recalibration request
        else if (messageType == RESET_CALIBRATION) {
            recalibrate(); // Trigger recalibration
        }

        // Handle connection test
        else if (messageType == 0x08) { // Example: Use 0x08 for CONNECTION_TEST
            Serial.println("ARDUINO_ONLINE"); // Respond to connection test
        }
    }

    // Read and send current weight to Raspberry Pi
    long weight = scale.get_units(3); // Apply calibration automatically
    Serial.write(CURRENT_WEIGHT); // Send the message type
    Serial.println(weight);       // Send the weight as a string
}

// Function to handle the fill process
void fill() {
    digitalWrite(LED_PIN, HIGH); // Turn LED ON at start of fill

    scale.tare();
    // Request target weight from Raspberry Pi
    Serial.write(REQUEST_TARGET_WEIGHT);

    String receivedData = "";
    float targetWeight = 0.0;

    // Wait to receive the target weight from the Raspberry Pi
    while (true) {
        if (Serial.available() > 0) {
            byte messageType = Serial.read(); // Read the message type
            if (messageType == TARGET_WEIGHT) { // Check for the TARGET_WEIGHT response
                receivedData = Serial.readStringUntil('\n'); // Read the target weight
                targetWeight = receivedData.toFloat(); // Convert to float
                break; // Exit the loop once the target weight is received
            } else if (messageType == RELAY_DEACTIVATED) { // Check for the RELAY_DEACTIVATED message
                Serial.println("E-Stop activated. Aborting fill process.");
                digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
                return; // Abort the fill function
            }
        }
    }

    // Request time limit from Raspberry Pi
    Serial.write(REQUEST_TIME_LIMIT);

    unsigned long timeLimit = 0;

    // Wait to receive the time limit from the Raspberry Pi
    while (true) {
        if (Serial.available() > 0) {
            byte messageType = Serial.read(); // Read the message type
            if (messageType == REQUEST_TIME_LIMIT) {
                receivedData = Serial.readStringUntil('\n'); // Read the time limit
                timeLimit = receivedData.toInt(); // Convert to integer
                break; // Exit the loop once the time limit is received
            } else if (messageType == RELAY_DEACTIVATED) { // Check for the RELAY_DEACTIVATED message
                Serial.println("E-Stop activated. Aborting fill process.");
                digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
                return; // Abort the fill function
            }
        }
    }

    // Start the validation process
    Serial.print("Target Weight Received: ");
    Serial.println(targetWeight);
    Serial.print("Time Limit Received: ");
    Serial.println(timeLimit);

    // Check the current weight on the scale
    long currentWeight = scale.get_units(3); // Get the current weight
    Serial.print("Current Weight: ");
    Serial.println(currentWeight);

    // If the current weight is greater than 20% of the target weight, abort the fill process
    if (currentWeight > 0.2 * targetWeight) {
        Serial.println("ERROR: CLEAR SCALE"); // Send error message to the Raspberry Pi
        digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
        return; // Exit the function without starting the fill process
    }

    // Start filling process
    unsigned long startTime = millis(); // Record the start time
    digitalWrite(RELAY_PIN, LOW);      // Turn relay ON

    while (scale.get_units(3) < targetWeight) { // Use 5 samples for faster response
        unsigned long currentTime = millis(); // Get the current time
        unsigned long elapsedTime = currentTime - startTime; // Calculate elapsed time
        timeLimit -= elapsedTime; // Subtract elapsed time from the time limit
        startTime = currentTime;  // Update the start time for the next iteration

        // Check if the time limit has been exceeded
        if (timeLimit <= 0) {
            Serial.println("ERROR: TIME LIMIT EXCEEDED"); // Send error message to the Raspberry Pi
            digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
            digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
            return; // Exit the function
        }

        // Check for E-Stop during the filling process
        if (Serial.available() > 0) {
            byte messageType = Serial.read(); // Read the message type
            if (messageType == RELAY_DEACTIVATED) { // Check for the RELAY_DEACTIVATED message
                Serial.println("E-Stop activated during filling. Aborting process.");
                digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
                digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
                return; // Abort the fill function
            }
        }

        delay(50); // Small delay to allow the loop to run faster
    }

    digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
    Serial.println("Filling Complete");
    digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill
}

// Function to handle recalibration
void recalibrate() {
    Serial.println("Starting recalibration...");

    // Continuously send current scale readings to the Raspberry Pi
    while (true) {
        long weight = scale.get_units(3);
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
        long weight = scale.get_units(3);
        Serial.print("Current Weight: ");
        Serial.println(weight);

        if (digitalRead(BUTTON_PIN) == LOW) {
            delay(200); // Debounce delay
            float rawUnits = scale.get_units(3); // Get the raw units
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