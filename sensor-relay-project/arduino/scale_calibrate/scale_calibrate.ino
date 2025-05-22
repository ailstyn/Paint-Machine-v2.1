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

  Serial.println("Press the button to begin calibration...");
  // Wait for button press (active LOW)
  while (digitalRead(BUTTON_PIN) != LOW) {
    delay(10);
  }
  // Debounce: wait for button release
  while (digitalRead(BUTTON_PIN) == LOW) {
    delay(10);
  }

  Serial.println("Remove all weight from scale.");
  Serial.println("Taring...");
  scale.set_scale();
  scale.tare();

  Serial.println("Taking 10 readings from empty scale...");
  long reading = scale.get_units(10);
  Serial.print("Empty scale reading: ");
  Serial.println(reading);

  Serial.println("Place a known weight on the scale.");
  Serial.println("Enter the weight in grams (e.g., 500), then press Enter:");
  while (!Serial.available());
  String input = Serial.readStringUntil('\n');
  float known_weight = input.toFloat();

  Serial.println("Taking 10 readings with known weight...");
  long known_reading = scale.get_units(10);
  Serial.print("Known weight reading: ");
  Serial.println(known_reading);

  if (known_weight > 0) {
    float calibration_factor = (float)(known_reading - reading) / known_weight;
    Serial.print("Suggested calibration factor: ");
    Serial.println(calibration_factor, 6);
    Serial.println("Use scale.set_scale(calibration_factor); in your code.");
  } else {
    Serial.println("Invalid weight entered.");
  }
}

void loop() {
  // Nothing to do here
}