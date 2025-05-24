#include <HX711.h>

// Pin definitions
#define LOADCELL_DOUT_PIN 3
#define LOADCELL_SCK_PIN 2
#define BUTTON_PIN 10

HX711 scale;
float scaleCalibration = 26049.0; // Set your calibration value here
const float correctWeight = 61.0; // Known correct weight in grams

void setup() {
  Serial.begin(9600);
  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  scale.set_scale(scaleCalibration);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  delay(3000); // Allow time for the scale to stabilize

  Serial.println("Taring scale...");
  scale.tare();
  Serial.println("Place weight on scale and press button to verify scale calibration");

  // Wait for button press (active LOW)
  while (digitalRead(BUTTON_PIN) != LOW) {
    delay(10);
  }
  // Debounce: wait for button release
  while (digitalRead(BUTTON_PIN) == LOW) {
    delay(10);
  }

  // Run calibration test
  Serial.println("Testing calibration value...");
  for (int i = 0; i < 10; i++) {
    float reading = scale.get_units(3);
    Serial.print(reading, 3);
    Serial.print(i + 1);
    Serial.print(": ");
  }

  Serial.println("Test complete. Press button to begin benchmark.")

  // Wait for button press (active LOW)
  while (digitalRead(BUTTON_PIN) != LOW) {
    delay(10);
  }
  // Debounce: wait for button release
  while (digitalRead(BUTTON_PIN) == LOW) {
    delay(10);
  }

  Serial.println("Button pressed, starting benchmark...");
  delay(1000); // Optional: short pause before starting
}

void loop() {
  for (int n = 1; n <= 10; n++) {
    Serial.print("\nTesting scale.get_units(");
    Serial.print(n);
    Serial.println(") with 25 samples...");

    float sum = 0, sumError = 0;
    float sampleTimes[25];
    float samples[25];

    unsigned long cycleStart = millis();
    for (int i = 0; i < 25; i++) {
      unsigned long t0 = millis();
      float val = scale.get_units(n);
      unsigned long t1 = millis();
      samples[i] = val;
      sampleTimes[i] = (float)(t1 - t0);

      sum += val;
      sumError += abs(val - correctWeight);
    }
    unsigned long cycleEnd = millis();

    Serial.print("Total time for 25 samples: ");
    Serial.print(cycleEnd - cycleStart);
    Serial.println(" ms");

    Serial.println("Individual sample times (ms):");
    float totalSampleTime = 0;
    for (int i = 0; i < 25; i++) {
      Serial.print(sampleTimes[i], 3);
      Serial.print(i < 24 ? ", " : "\n");
      totalSampleTime += sampleTimes[i];
    }
    float avgSampleTime = totalSampleTime / 25.0;
    Serial.print("Average sample time: ");
    Serial.print(avgSampleTime, 3);
    Serial.println(" ms");

    Serial.print("Average error from 61g: ");
    Serial.println(sumError / 25.0, 3);

    float avgError = sumError / 25.0;
    float avgErrorPercent = (avgError / correctWeight) * 100.0;

    Serial.print("Average error from 61g: ");
    Serial.print(avgError, 3);
    Serial.print(" (");
    Serial.print(avgErrorPercent, 2);
    Serial.println("%)");

    float avgMeasured = sum / 25.0;
    float percentOfCorrect = (avgMeasured / correctWeight) * 100.0;

    Serial.print("Average measured value: ");
    Serial.print(avgMeasured, 3);
    Serial.print(" (");
    Serial.print(percentOfCorrect, 2);
    Serial.println("% of correct weight)");

    Serial.println("----");
    delay(3000); // Wait before next n
  }

  Serial.println("Benchmark complete. Restart Arduino to run again.");
  while (1); // Stop after one full run
}