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
#define RELAY_DEACTIVATED 0xFA
#define VERBOSE_DEBUG 0xFE
#define BEGIN_FILL 0x10

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
    // Blink LED 3 times to indicate setup complete
    for (int i = 0; i < 3; i++) {
        digitalWrite(LED_PIN, HIGH);
        delay(1000);
        digitalWrite(LED_PIN, LOW);
        delay(1000);
    }
    Serial.begin(9600);
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
    delay(1000);
    scale.set_scale(scaleCalibration); // Set the initial calibration value
    scale.tare(); // Tare the scale

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
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Calibration value received and applied: ");
    Serial.println(scaleCalibration);
}

void loop() {
        if (digitalRead(BUTTON_PIN) == LOW) {
        fill();
    }

    // Check for incoming serial messages
    if (Serial.available() > 0) {
        byte messageType = Serial.read();

        // Handle tare command
        if (messageType == TARE_SCALE) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("Taring scale...");
            scale.tare();
            Serial.write(VERBOSE_DEBUG);
            Serial.println("Scale tared.");
        }

        // Handle recalibration request
        else if (messageType == RESET_CALIBRATION) {
            recalibrate();
        }
    }

    // Read and send current weight to Raspberry Pi
    long weight = scale.get_units(3);
    Serial.write(CURRENT_WEIGHT);
    Serial.println(weight);
}

// Function to handle the fill process
void fill() {
    digitalWrite(LED_PIN, HIGH); // Turn LED ON at start of fill

    scale.tare();

    Serial.write(BEGIN_FILL); // Send BEGIN_FILL as a byte

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
    Serial.write(REQUEST_TIME_LIMIT); // Send request
    delay(200);

    unsigned long timeLimit = 0;
    if (Serial.available() > 0) {
        byte messageType = Serial.read();
        if (messageType == REQUEST_TIME_LIMIT) {
            String receivedData = Serial.readStringUntil('\n');
            timeLimit = receivedData.toInt();
            Serial.write(VERBOSE_DEBUG);
            Serial.print("Received time limit: ");
            Serial.println(timeLimit);
        } else if (messageType == RELAY_DEACTIVATED) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("E-Stop activated. Aborting fill process.");
            digitalWrite(LED_PIN, LOW);
            return;
        }
    } else {
        Serial.write(VERBOSE_DEBUG);
        Serial.println("No time limit received from Pi.");
        digitalWrite(LED_PIN, LOW);
        return;
    }

    // Start the validation process
    Serial.write(VERBOSE_DEBUG);
    Serial.println("Target Weight Received: " + String(targetWeight));
    Serial.write(VERBOSE_DEBUG);
    Serial.println("Time Limit Received: " + String(timeLimit));

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

    unsigned long fillStartTime = millis();
    unsigned long fillEndTime = fillStartTime + timeLimit;

    while (scale.get_units(3) < targetWeight) { // Use 5 samples for faster response
        unsigned long now = millis();
        if (now >= fillEndTime) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("TIME LIMIT REACHED");
            digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
            digitalWrite(LED_PIN, LOW);    // Turn LED OFF at end of fill
            return;
        }

        // Read and send current weight to Raspberry Pi
        long currentWeight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.println(currentWeight);
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