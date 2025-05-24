#include <HX711.h>

// Pin definitions (adjust as needed)
#define LOADCELL_DOUT_PIN  3
#define LOADCELL_SCK_PIN   2
#define LED_PIN 16
#define BUTTON_PIN  10

HX711 scale;

void setup() {
  Serial.begin(9600);
  Serial.println("HX711 Calibration Sketch");
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, HIGH);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  scale.begin(LOADCELL_DOUT_PIN, LOADCELL_SCK_PIN);
  delay(3000);

  float calibration_factors[3];

  for (int trial = 0; trial < 3; trial++) {
    Serial.print("\n--- Calibration Run ");
    Serial.print(trial + 1);
    Serial.println(" of 3 ---");

    Serial.println("Press the button to begin calibration...");
    while (digitalRead(BUTTON_PIN) != LOW) { delay(10); }
    while (digitalRead(BUTTON_PIN) == LOW) { delay(10); }

    Serial.println("Remove all weight from scale and press the button...");
    while (digitalRead(BUTTON_PIN) != LOW) { delay(10); }
    while (digitalRead(BUTTON_PIN) == LOW) { delay(10); }
    Serial.println("Taking empty reading...");
    scale.set_scale(); // Reset scale to default
    scale.tare(); // Tare the scale
    long reading_empty = scale.get_units(10);
    Serial.print("Empty reading: ");
    Serial.println(reading_empty);

    Serial.println("Place known weight on scale and press the button...");
    while (digitalRead(BUTTON_PIN) != LOW) { delay(10); }
    while (digitalRead(BUTTON_PIN) == LOW) { delay(10); }
    Serial.println("Enter the weight in grams (e.g., 61), then press Enter:");
    while (!Serial.available());
    String input = Serial.readStringUntil('\n');
    float known_weight = input.toFloat();

    Serial.println("Taking reading with known weight...");
    long reading_with_weight = scale.get_units(10);
    Serial.print("Reading with weight: ");
    Serial.println(reading_with_weight);

    float calibration_factor = (float)(reading_with_weight - reading_empty) / known_weight;
    calibration_factors[trial] = calibration_factor;
    Serial.print("Suggested calibration factor for run ");
    Serial.print(trial + 1);
    Serial.print(": ");
    Serial.println(calibration_factor, 6);
    Serial.println("Use scale.set_scale(calibration_factor); in your code.");
  }

  // Print all three calibration factors and their average
  Serial.println("\n--- Calibration Results ---");
  float sum = 0;
  for (int i = 0; i < 3; i++) {
    Serial.print("Calibration factor ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(calibration_factors[i], 6);
    sum += calibration_factors[i];
  }
  float avg = sum / 3.0;
  Serial.print("Average calibration factor: ");
  Serial.println(avg, 6);
}

void loop() {
  // Nothing to do here
}