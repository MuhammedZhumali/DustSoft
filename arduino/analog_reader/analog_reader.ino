const unsigned long SAMPLE_INTERVAL_MS = 100;

const int MAIN_SENSOR_PIN = A0;
const int SECOND_SENSOR_PIN = A4;

unsigned long lastSampleMs = 0;

void setup() {
  Serial.begin(9600);
}

void loop() {
  unsigned long now = millis();
  if (now - lastSampleMs < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSampleMs = now;

  int a0 = analogRead(MAIN_SENSOR_PIN);
  int a4 = analogRead(SECOND_SENSOR_PIN);

  Serial.print("A0:");
  Serial.print(a0);
  Serial.print(" A4:");
  Serial.println(a4);
}
