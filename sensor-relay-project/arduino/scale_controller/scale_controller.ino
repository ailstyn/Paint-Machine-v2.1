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
#define FINAL_WEIGHT 0x11
#define CALIBRATION_STEP_DONE 0x12
#define CALIBRATION_CONTINUE  0x13
#define CALIBRATION_WEIGHT 0x14
#define FILL_TIME 0x15
#define MANUAL_FILL_START 0x20
#define MANUAL_FILL_END 0x21
#define EXIT_MANUAL_END 0x22
#define SMART_FILL_START 0x30
#define SMART_FILL_END   0x31
#define GET_ID 0xA0
#define STATION_ID 3
#define STOP 0xFD
#define CONFIRM_ID 0xA1

// Global variables
HX711 scale;
float scaleCalibration = 427.530059; // Default calibration value
float calibWeight = 61.0;     // Calibration weight in grams
float cWeight1 = 0.0; // Variable to store the calibration value
float cWeight2 = 0.0; // Variable to store the calibration value

void handshake_station_id() {
    const int blink_interval = 125;
    bool led_state = false;
    unsigned long last_blink = millis();
    static unsigned long last_send = 0;

    while (true) {
        unsigned long now = millis();
        if (now - last_blink >= blink_interval) {
            led_state = !led_state;
            digitalWrite(LED_PIN, led_state ? HIGH : LOW);
            last_blink = now;
        }
        if (now - last_send >= 250) {
            Serial.println("<ID:" + String(STATION_ID) + ">");
            last_send = now;
        }
        while (Serial.available() > 0) {
            byte cmd = Serial.read();
            if (cmd == CONFIRM_ID) {
                digitalWrite(LED_PIN, LOW);
                delay(100);
                return;
            }
        }
        delay(5);
    }
}

void request_and_apply_calibration() {
    // Request calibration from Pi
    while (true) {
        Serial.write(REQUEST_CALIBRATION);
        unsigned long start = millis();
        bool received = false;
        while (millis() - start < 500) {
            if (Serial.available() > 0) {
                byte messageType = Serial.read();
                if (messageType == REQUEST_CALIBRATION) {
                    String receivedData = Serial.readStringUntil('\n');
                    scaleCalibration = receivedData.toFloat();
                    scale.set_scale(scaleCalibration);
                    received = true;
                    break;
                }
            }
        }
        if (received) break;
    }

    // Print the received calibration value for debugging
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Calibration value received and applied: ");
    Serial.println(scaleCalibration);
}

void setup() {
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, HIGH);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    Serial.begin(9600);
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
    delay(1000);
    scale.set_scale(scaleCalibration); // Set the initial calibration value
    scale.tare(); // Tare the scale

    handshake_station_id();

    request_and_apply_calibration();
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
        else if (messageType == MANUAL_FILL_START) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("Manual fill started.");
        }
        else {
            // Serial.println("<ERR:Unknown message type received: " + String(messageType) + ">");
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

    // Request target weight from Raspberry Pi
    Serial.write(REQUEST_TARGET_WEIGHT);

    String receivedData = "";
    float targetWeight = 0.0;

    // Wait to receive the target weight from the Raspberry Pi
    while (true) {
        if (Serial.available() > 0) {
            byte messageType = Serial.read();
            if (messageType == TARGET_WEIGHT) {
                receivedData = Serial.readStringUntil('\n');
                targetWeight = receivedData.toFloat();
                break;
            } else if (messageType == STOP) {
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
        // Serial.println("<ERR:No time limit received from Pi>");
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
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Current Weight: ");
    Serial.println(currentWeight);

    // If the current weight is greater than 20% of the target weight, abort the fill process
    if (currentWeight > 0.2 * targetWeight) {
        // Serial.println("<ERR:CLEAR SCALE>");
        digitalWrite(LED_PIN, LOW);
        return;
    }

    // Start filling process
    unsigned long startTime = millis(); // Record the start time
    digitalWrite(RELAY_PIN, LOW);      // Turn relay ON

    unsigned long fillStartTime = millis();
    unsigned long fillEndTime = fillStartTime + timeLimit;

    while (scale.get_units(3) < targetWeight) { // Use 5 samples for faster response
        unsigned long now = millis();
        long currentWeight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.println(currentWeight);
        if (now >= fillEndTime) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("TIME LIMIT REACHED");
            digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
            digitalWrite(LED_PIN, LOW);    // Turn LED OFF at end of fill

            // Report final weight
            long finalWeight = scale.get_units(3);
            Serial.write(FINAL_WEIGHT);
            Serial.println(finalWeight);

            // Report fill time
            unsigned long fillTime = now - fillStartTime;
            Serial.write(FILL_TIME);
            Serial.println(fillTime);

            return;
        }
    }

    // If fill ended because target weight was reached:
    digitalWrite(RELAY_PIN, HIGH); // Turn relay OFF
    Serial.write(VERBOSE_DEBUG);
    Serial.println("TARGET WEIGHT REACHED");
    digitalWrite(LED_PIN, LOW);  // Turn LED OFF at end of fill

    // Report final weight
    long finalWeight = scale.get_units(3);
    Serial.write(FINAL_WEIGHT);
    Serial.println(finalWeight);

    // Report fill time
    unsigned long fillTime = millis() - fillStartTime;
    Serial.write(FILL_TIME);
    Serial.println(fillTime);
}

// Function to handle recalibration
void recalibrate() {
    Serial.println("Starting recalibration...");
    digitalWrite(LED_PIN, HIGH); // Turn LED ON during calibration
    // --- Step 1: Ask user to clear the scale ---
    while (true) {
        long weight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.println(weight);

        // Check for "step complete" message from Pi
        if (Serial.available() > 0) {
            byte msg = Serial.read();
            if (msg == CALIBRATION_CONTINUE) {
                break; // Proceed to next step
            }
        }
    }
    digitalWrite(LED_PIN, LOW); // Turn LED OFF after clearing scale
    scale.tare();
    scale.set_scale();
    scale.tare();
    long cWeight1 = scale.get_units(10);
    delay(500);
    Serial.write(CALIBRATION_STEP_DONE);

    // --- Step 2: Wait for user to place calibration weight ---
    while (true) {
        // Check for "step complete" message from Pi
        if (Serial.available() > 0) {
            byte msg = Serial.read();
            if (msg == CALIBRATION_WEIGHT) {
                String receivedData = Serial.readStringUntil('\n'); // Read the calibration weight
                calibWeight = receivedData.toFloat(); // Convert to float
                delay(100); // Allow time for the weight to stabilize
                Serial.write(CALIBRATION_STEP_DONE);
                delay(200); // Allow time for the message to be sent
                break;
            }
        }
    }
    long cWeight2 = scale.get_units(10);
    delay(500);
    Serial.write(CALIBRATION_STEP_DONE);

    // --- Step 3: Calculate and set new calibration value ---
    float delta = cWeight2 - cWeight1;
    if (calibWeight != 0) {
        scaleCalibration = delta / calibWeight;
        scale.set_scale(scaleCalibration);
    } else {
        // Serial.println("<ERR:Calibration weight is zero>");
    }

    // Send the new calibration value to the Pi
    Serial.write(CALIBRATION_WEIGHT);
    Serial.println(scaleCalibration);

    // Optionally send step done and debug info
    Serial.write(CALIBRATION_STEP_DONE);
}

// Manual fill function: allows repeated press/release cycles without restarting the function
void manual_fill() {
    digitalWrite(RELAY_PIN, HIGH); // Ensure relay is OFF initially

    while (true) {
        // Wait for button press, send weight updates while waiting
        while (digitalRead(BUTTON_PIN) == HIGH) {
            long weight = scale.get_units(3);
            Serial.write(CURRENT_WEIGHT);
            Serial.println(weight);

            if (Serial.available() > 0) {
                byte msg = Serial.read();
                if (msg == EXIT_MANUAL_END) return;
            }
        }

        // Button pressed, open relay
        digitalWrite(RELAY_PIN, LOW); // Relay ON (active low)

        // Keep relay open while button is held, send weight updates
        while (digitalRead(BUTTON_PIN) == LOW) {
            long weight = scale.get_units(3);
            Serial.write(CURRENT_WEIGHT);
            Serial.println(weight);

            if (Serial.available() > 0) {
                // Example: exit manual fill if a specific byte is received
                byte msg = Serial.read();
                if (msg == MANUAL_FILL_END) {
                    digitalWrite(RELAY_PIN, HIGH); // Relay OFF
                    return;
                }
            }
        }

        // Button released, close relay
        digitalWrite(RELAY_PIN, HIGH); // Relay OFF
    }
}

void smart_fill() {
    scale.tare();

    // Request target weight from Raspberry Pi
    Serial.write(REQUEST_TARGET_WEIGHT);

    String receivedData = "";
    float targetWeight = 0.0;

    // Wait to receive the target weight from the Raspberry Pi
    while (true) {
        if (Serial.available() > 0) {
            byte messageType = Serial.read();
            if (messageType == TARGET_WEIGHT) {
                receivedData = Serial.readStringUntil('\n');
                targetWeight = receivedData.toFloat();
                break;
            } else if (messageType == RELAY_DEACTIVATED) {
                Serial.println("E-Stop activated. Aborting smart fill.");
                digitalWrite(LED_PIN, LOW);
                return;
            }
        }
    }

    digitalWrite(RELAY_PIN, HIGH); // Turn relay ON
    Serial.write(SMART_FILL_START);

    // Wait for weight to start increasing (paint arrives)
    long baselineWeight = scale.get_units(3);
    long startWeight = baselineWeight;
    unsigned long startTime = millis();
    const long threshold = 2; // grams, adjust as needed
    const unsigned long maxWait = 3000; // ms, timeout to avoid infinite wait

    unsigned long waitStart = millis();
    while (true) {
        long currentWeight = scale.get_units(3);
        if (currentWeight - baselineWeight >= threshold) {
            startWeight = currentWeight;
            startTime = millis();
            break;
        }
        if (millis() - waitStart > maxWait) {
            startWeight = baselineWeight;
            startTime = waitStart;
            break;
        }
        delay(10);
    }

    unsigned long fillStartTime = startTime;
    long halfWeight = startWeight;
    unsigned long halfTime = startTime;
    long endWeight = startWeight;
    unsigned long endTime = startTime;

    // 1. Fill until 50% of target weight
    while (true) {
        long weight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.println(weight);

        if (weight >= (targetWeight * 0.5)) {
            halfWeight = weight;
            halfTime = millis();
            break;
        }

        // Optional: timeout check here if needed
    }

    // 2. Calculate flow rate (g/ms) using start and halfway point
    float deltaWeight = halfWeight - startWeight;
    unsigned long deltaTime = halfTime - startTime;
    float flowRate = 0.0;
    if (deltaTime > 0) {
        flowRate = deltaWeight / (float)deltaTime; // g/ms
    }

    // 3. Predict remaining time to reach target weight
    float remainingWeight = targetWeight - halfWeight;
    unsigned long predictedTime = 0;
    if (flowRate > 0) {
        predictedTime = (unsigned long)(remainingWeight / flowRate);
    }

    // 4. Continue filling for the predicted time
    unsigned long predictedEnd = millis() + predictedTime;
    while (millis() < predictedEnd) {
        long weight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.println(weight);
        delay(10); // Don't hammer the scale
    }

    // 5. Stop filling
    digitalWrite(RELAY_PIN, LOW); // Turn relay OFF
    Serial.write(SMART_FILL_END);

    // 6. Final weight and flow rate reporting
    endWeight = scale.get_units(3);
    endTime = millis();

    Serial.write(VERBOSE_DEBUG);
    Serial.print("Flow rate (g/ms): ");
    Serial.println(flowRate, 6);
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Final weight: ");
    Serial.println(endWeight);
}