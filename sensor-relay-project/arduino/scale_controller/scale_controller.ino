#include <EEPROM.h>
#include <HX711.h>

// ================= PIN DEFINITIONS =================
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2
#define RELAY_PIN 21
#define BUTTON_PIN 10
#define LED_PIN 16

// ================= PROTOCOL BYTES ==================
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
#define STOP 0xFD
#define CONFIRM_ID 0xA1
#define RESET_HANDSHAKE 0xB0
#define BUTTON_ERROR 0xE0
#define MAX_WEIGHT_WARNING 0xE1
#define MAX_WEIGHT_END 0xE2
#define SERIAL_MAX_LEN 16
#define SCALE_MAX_GRAMS 1000
#define TARE_CONFIRMED 0x0A

// ================= GLOBAL VARIABLES ================
HX711 scale;
float scaleCalibration = 427.530059; // Default calibration value
float calibWeight = 61.0;            // Calibration weight in grams
float cWeight1 = 0.0, cWeight2 = 0.0;
float trueBaseline = 0.0;            // The initial tare value at startup
float tareOffset = 0.0;              // Offset to adjust the tare value
char station_serial[SERIAL_MAX_LEN] = {0};

// ================= UTILITY FUNCTIONS ==============

void read_serial_from_eeprom() {
    for (int i = 0; i < SERIAL_MAX_LEN; ++i) {
        station_serial[i] = EEPROM.read(i);
        if (station_serial[i] == '\0') break;
    }
}

// Always use this for taring so tareOffset is tracked
void tare_and_update_offset() {
    float beforeTare = scale.get_units(3);
    scale.tare();
    tareOffset += beforeTare;
}

// Get the true weight on the scale, regardless of taring
float get_true_weight(long currentWeight) {
    return currentWeight + tareOffset;
}

// ================= HANDSHAKE & CALIBRATION =============

void handshake_station_id() {
    const int blink_interval = 125;
    bool led_state = false;
    unsigned long last_blink = millis();
    const char handshake_seq[] = "PMID";
    int handshake_pos = 0;

    // 1. Blink and wait for 'PMID' sequence
    while (true) {
        unsigned long now = millis();
        if (now - last_blink >= blink_interval) {
            led_state = !led_state;
            digitalWrite(LED_PIN, led_state ? HIGH : LOW);
            last_blink = now;
        }
        if (Serial.available() > 0) {
            char c = Serial.read();
            if (c == handshake_seq[handshake_pos]) {
                handshake_pos++;
                if (handshake_seq[handshake_pos] == '\0') {
                        break; // Full sequence received
                }
            } else {
                handshake_pos = 0;
            }
        }
        delay(5);
    }

        // After receiving PMID, turn LED off
        digitalWrite(LED_PIN, LOW);
        delay(500);

        // Send serial, then turn LED on
        Serial.print("<SERIAL:");
        Serial.print(station_serial);
        Serial.println(">");
        digitalWrite(LED_PIN, HIGH);

        // Wait for CONFIRM_ID, then turn LED off
        while (true) {
            if (Serial.available() > 0) {
                byte cmd = Serial.read();
                if (cmd == CONFIRM_ID) break;
            }
            delay(5);
        }
        delay(200);
        digitalWrite(LED_PIN, LOW);
}

void request_and_apply_calibration() {
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
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Calibration value received and applied: ");
    Serial.println(scaleCalibration);
}

// ================== SETUP =========================

void setup() {
    pinMode(RELAY_PIN, OUTPUT);
    digitalWrite(RELAY_PIN, HIGH);
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    Serial.begin(9600);
    scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
    delay(1000);
    scale.set_scale(scaleCalibration);

    tare_and_update_offset(); // Tare and set tareOffset
    trueBaseline = scale.get_units(10); // Store the initial baseline after tare
    tareOffset = 0.0; // At startup, tareOffset is zero

    read_serial_from_eeprom();
    handshake_station_id();
    request_and_apply_calibration();
}

// ================== MAIN LOOP =====================

const unsigned long BUTTON_STUCK_THRESHOLD = 3000; // 3 seconds

void handle_max_weight_block() {
    // Shut off relay, blink LED, and block until weight < 50g
    digitalWrite(RELAY_PIN, HIGH); // Relay OFF
    unsigned long lastBlink = 0;
    bool ledState = false;
    bool sentEnd = false;
    static bool sentWarning = false;
    sentWarning = false; // Reset for each call

    while (true) {
        long currentWeight = scale.get_units(3); // Get the raw weight
        float trueWeight = get_true_weight(currentWeight); // Pass it in

        // --- Send current weight to GUI for live update ---
        Serial.write(CURRENT_WEIGHT);
        Serial.write((byte*)&currentWeight, sizeof(currentWeight));

        // Blink LED every 300ms
        unsigned long now = millis();
        if (now - lastBlink > 300) {
            ledState = !ledState;
            digitalWrite(LED_PIN, ledState ? HIGH : LOW);
            lastBlink = now;
        }

        // If weight drops below 50g, break out after a short delay and send MAX_WEIGHT_END
        if (abs(trueWeight) < 50.0) {
            digitalWrite(LED_PIN, LOW);
            delay(1500); // Wait a bit to ensure it's really clear
            if (!sentEnd) {
                Serial.write(MAX_WEIGHT_END);
                Serial.println("<INFO:MAX WEIGHT CLEARED>");
                sentEnd = true;
            }
            break;
        }

        // If not already sent, send the warning
        if (!sentWarning) {
            Serial.write(MAX_WEIGHT_WARNING);
            Serial.println("<ERR:MAX WEIGHT EXCEEDED>");
            sentWarning = true;
        }

        delay(10); // Small delay to avoid busy loop
    }
}

void loop() {
    static unsigned long buttonLowStart = 0;
    static bool buttonWasStuck = false;

    // --- MAX WEIGHT CHECK ---
    long currentWeight = scale.get_units(3); // Get the raw weight
    float trueWeight = get_true_weight(currentWeight); // Pass it in
    if (trueWeight >= SCALE_MAX_GRAMS) {
        handle_max_weight_block();
        return;
    }

    // --- BUTTON STUCK CHECK ---
    if (digitalRead(BUTTON_PIN) == LOW) {
        if (buttonLowStart == 0) {
            buttonLowStart = millis();
        } else if ((millis() - buttonLowStart) > BUTTON_STUCK_THRESHOLD) {
            if (!buttonWasStuck) {
                digitalWrite(LED_PIN, HIGH);
                Serial.write(BUTTON_ERROR);
                Serial.println("<ERR:BUTTON STUCK>");
                buttonWasStuck = true;
            }
        }
    } else {
        if (buttonLowStart != 0 && !buttonWasStuck) {
            fill();
        }
        buttonLowStart = 0;
        buttonWasStuck = false;
        digitalWrite(LED_PIN, LOW);
    }

    // --- SERIAL COMMANDS ---
    if (Serial.available() > 0) {
        byte messageType = Serial.read();
        if (messageType == TARE_SCALE) {
            tare_and_update_offset();
            Serial.write(TARE_CONFIRMED); // Send confirmation byte ONLY after taring
        } else if (messageType == RESET_CALIBRATION) {
            recalibrate();
        } else if (messageType == MANUAL_FILL_START) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("Manual fill started.");
            manual_fill();
        }
        if (messageType == GET_ID) {
            Serial.write(VERBOSE_DEBUG);
            Serial.println("Resetting handshake...");
            handshake_station_id();
            request_and_apply_calibration();
        }
    }

    // --- SEND CURRENT WEIGHT ---
    long weight = scale.get_units(3);
    Serial.write(CURRENT_WEIGHT);
    Serial.write((byte*)&weight, sizeof(weight));
}

// ================== FILL FUNCTIONS =================

void fill() {
    digitalWrite(LED_PIN, HIGH);

    Serial.write(REQUEST_TARGET_WEIGHT);
    String receivedData = "";
    float targetWeight = 0.0;

    while (true) {
        if (Serial.available() > 0) {
            byte messageType = Serial.read();
            if (messageType == TARGET_WEIGHT) {
                receivedData = Serial.readStringUntil('\n');
                targetWeight = receivedData.toFloat();
                break;
            } else if (messageType == STOP) {
                Serial.println("E-Stop activated. Aborting fill process.");
                digitalWrite(LED_PIN, LOW);
                return;
            }
        }
    }

    Serial.write(REQUEST_TIME_LIMIT);
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
        digitalWrite(LED_PIN, LOW);
        return;
    }

    Serial.write(VERBOSE_DEBUG);
    Serial.println("Target Weight Received: " + String(targetWeight));
    Serial.write(VERBOSE_DEBUG);
    Serial.println("Time Limit Received: " + String(timeLimit));

    long currentWeight = scale.get_units(3);
    float trueWeight = get_true_weight(currentWeight);
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Current Weight: ");
    Serial.println(currentWeight);

    if (trueWeight > 0.2 * targetWeight) {
        digitalWrite(LED_PIN, LOW);
        return;
    }

    unsigned long startTime = millis();
    digitalWrite(RELAY_PIN, LOW);
    unsigned long fillStartTime = millis();
    unsigned long fillEndTime = fillStartTime + timeLimit;

    Serial.write(BEGIN_FILL);

    while (scale.get_units(3) < targetWeight) {
        unsigned long now = millis();
        long currentWeight = scale.get_units(3);
        float trueWeight = get_true_weight(currentWeight);

        // Max weight check during fill
        if (trueWeight >= SCALE_MAX_GRAMS) {
            Serial.write(MAX_WEIGHT_WARNING);
            Serial.println("<ERR:MAX WEIGHT DURING FILL>");
            digitalWrite(RELAY_PIN, HIGH);
            digitalWrite(LED_PIN, HIGH);
            handle_max_weight_block();
            // After block, resume fill loop
            digitalWrite(RELAY_PIN, LOW);
            digitalWrite(LED_PIN, HIGH);
            continue;
        }

        Serial.write(CURRENT_WEIGHT);
        Serial.write((byte*)&currentWeight, sizeof(currentWeight));
        if (now >= fillEndTime) {
            digitalWrite(RELAY_PIN, HIGH);
            digitalWrite(LED_PIN, LOW);

            long finalWeight = scale.get_units(3);
            Serial.write(FINAL_WEIGHT);
            Serial.write((byte*)&finalWeight, sizeof(finalWeight));
            unsigned long fillTime = now - fillStartTime;
            Serial.write(FILL_TIME);
            Serial.write((byte*)&fillTime, sizeof(fillTime));
            return;
        }
    }

    digitalWrite(RELAY_PIN, HIGH);
    Serial.write(VERBOSE_DEBUG);
    Serial.println("TARGET WEIGHT REACHED");
    digitalWrite(LED_PIN, LOW);

    long finalWeight = scale.get_units(3);
    Serial.write(FINAL_WEIGHT);
    Serial.write((byte*)&finalWeight, sizeof(finalWeight));

    unsigned long fillTime = millis() - fillStartTime;
    Serial.write(FILL_TIME);
    Serial.write((byte*)&fillTime, sizeof(fillTime));
}

void manual_fill() {
    digitalWrite(RELAY_PIN, HIGH);
    digitalWrite(LED_PIN, LOW);

    while (true) {
        while (digitalRead(BUTTON_PIN) == HIGH) {
            long weight = scale.get_units(3);
            float trueWeight = get_true_weight(weight);

            // Max weight check during manual idle
            if (trueWeight >= SCALE_MAX_GRAMS) {
                Serial.write(MAX_WEIGHT_WARNING);
                Serial.println("<ERR:MAX WEIGHT DURING MANUAL (IDLE)>");
                digitalWrite(RELAY_PIN, HIGH);
                digitalWrite(LED_PIN, HIGH);
                handle_max_weight_block();
                // After block, resume idle loop
                digitalWrite(RELAY_PIN, HIGH);
                digitalWrite(LED_PIN, LOW);
                continue;
            }

            Serial.write(CURRENT_WEIGHT);
            Serial.write((byte*)&weight, sizeof(weight));
            digitalWrite(LED_PIN, LOW);

            if (Serial.available() > 0) {
                byte msg = Serial.read();
                if (msg == EXIT_MANUAL_END) return;
            }
        }
        digitalWrite(RELAY_PIN, LOW);

        while (digitalRead(BUTTON_PIN) == LOW) {
            long weight = scale.get_units(3);
            float trueWeight = get_true_weight(weight);

            // Max weight check during manual fill
            if (trueWeight >= SCALE_MAX_GRAMS) {
                Serial.write(MAX_WEIGHT_WARNING);
                Serial.println("<ERR:MAX WEIGHT DURING MANUAL>");
                digitalWrite(RELAY_PIN, HIGH);
                digitalWrite(LED_PIN, HIGH);
                handle_max_weight_block();
                // After block, resume fill loop
                digitalWrite(RELAY_PIN, LOW);
                digitalWrite(LED_PIN, HIGH);
                continue;
            }

            digitalWrite(LED_PIN, HIGH);
            Serial.write(CURRENT_WEIGHT);
            Serial.write((byte*)&weight, sizeof(weight));

            if (Serial.available() > 0) {
                byte msg = Serial.read();
                if (msg == MANUAL_FILL_END) {
                    digitalWrite(RELAY_PIN, HIGH);
                    return;
                }
            }
        }
        digitalWrite(RELAY_PIN, HIGH);
    }
}

void smart_fill() {
    tare_and_update_offset();

    Serial.write(REQUEST_TARGET_WEIGHT);
    String receivedData = "";
    float targetWeight = 0.0;

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

    digitalWrite(RELAY_PIN, HIGH);
    Serial.write(SMART_FILL_START);

    long baselineWeight = scale.get_units(3);
    long startWeight = baselineWeight;
    unsigned long startTime = millis();
    const long threshold = 2;
    const unsigned long maxWait = 3000;

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
        float trueWeight = get_true_weight(weight);

        // Max weight check during smart fill
        if (trueWeight >= SCALE_MAX_GRAMS) {
            Serial.write(MAX_WEIGHT_WARNING);
            Serial.println("<ERR:MAX WEIGHT DURING SMART>");
            digitalWrite(RELAY_PIN, HIGH);
            digitalWrite(LED_PIN, HIGH);
            handle_max_weight_block();
            // After block, resume smart fill loop
            digitalWrite(RELAY_PIN, LOW);
            digitalWrite(LED_PIN, HIGH);
            continue;
        }

        Serial.write(CURRENT_WEIGHT);
        Serial.write((byte*)&weight, sizeof(weight));

        if (weight >= (targetWeight * 0.5)) {
            halfWeight = weight;
            halfTime = millis();
            break;
        }
    }

    float deltaWeight = halfWeight - startWeight;
    unsigned long deltaTime = halfTime - startTime;
    float flowRate = 0.0;
    if (deltaTime > 0) {
        flowRate = deltaWeight / (float)deltaTime;
    }

    float remainingWeight = targetWeight - halfWeight;
    unsigned long predictedTime = 0;
    if (flowRate > 0) {
        predictedTime = (unsigned long)(remainingWeight / flowRate);
    }

    unsigned long predictedEnd = millis() + predictedTime;
    while (millis() < predictedEnd) {
        long weight = scale.get_units(3);
        float trueWeight = get_true_weight(weight);

        // Max weight check during smart fill
        if (trueWeight >= SCALE_MAX_GRAMS) {
            Serial.write(MAX_WEIGHT_WARNING);
            Serial.println("<ERR:MAX WEIGHT DURING SMART>");
            digitalWrite(RELAY_PIN, HIGH);
            digitalWrite(LED_PIN, HIGH);
            handle_max_weight_block();
            // After block, resume smart fill loop
            digitalWrite(RELAY_PIN, LOW);
            digitalWrite(LED_PIN, HIGH);
            continue;
        }

        Serial.write(CURRENT_WEIGHT);
        Serial.write((byte*)&weight, sizeof(weight));
        delay(10);
    }
    Serial.print("Final weight: ");
    Serial.println(endWeight);
    digitalWrite(RELAY_PIN, LOW);
    Serial.write(SMART_FILL_END);

    endWeight = scale.get_units(3);
    endTime = millis();

    Serial.write(VERBOSE_DEBUG);
    Serial.print("Flow rate (g/ms): ");
    Serial.println(flowRate, 6);
    Serial.write(VERBOSE_DEBUG);
    Serial.print("Final weight: ");
    Serial.println(endWeight);
}

// ================== CALIBRATION ====================

void recalibrate() {
    Serial.println("Starting recalibration...");
    digitalWrite(LED_PIN, HIGH);

    // Step 1: Clear scale
    while (true) {
        long weight = scale.get_units(3);
        Serial.write(CURRENT_WEIGHT);
        Serial.write((byte*)&weight, sizeof(weight));
        if (Serial.available() > 0) {
            byte msg = Serial.read();
            if (msg == CALIBRATION_CONTINUE) break;
        }
    }
    digitalWrite(LED_PIN, LOW);
    tare_and_update_offset();
    scale.set_scale();
    tare_and_update_offset();
    long cWeight1 = scale.get_units(10);
    delay(500);
    Serial.write(CALIBRATION_STEP_DONE);

    // Step 2: Place calibration weight
    while (true) {
        if (Serial.available() > 0) {
            byte msg = Serial.read();
            if (msg == CALIBRATION_WEIGHT) {
                String receivedData = Serial.readStringUntil('\n');
                calibWeight = receivedData.toFloat();
                delay(100);
                Serial.write(CALIBRATION_STEP_DONE);
                delay(200);
                break;
            }
        }
    }
    long cWeight2 = scale.get_units(10);
    delay(500);
    Serial.write(CALIBRATION_STEP_DONE);

    // Step 3: Calculate and set new calibration value
    float delta = cWeight2 - cWeight1;
    if (calibWeight != 0) {
        scaleCalibration = delta / calibWeight;
        scale.set_scale(scaleCalibration);
    }
    Serial.write(CALIBRATION_WEIGHT);
    Serial.println(scaleCalibration);
    Serial.write(CALIBRATION_STEP_DONE);
}