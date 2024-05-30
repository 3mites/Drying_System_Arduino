const int fanPin = 9;  // PWM pin connected to the fan

void setup() {
  pinMode(fanPin, OUTPUT);
  Serial.begin(9600);  // Start serial communication for debugging
}

void loop() {
  // Test at full speed
  analogWrite(fanPin, 240);
  Serial.print("PWM Value: ");
  Serial.println(255);
  delay(5000);  // Run for 5 seconds
  // Test at quarter speed
  analogWrite(fanPin, 0);
  Serial.print("PWM Value: ");
  Serial.println(64);
  delay(5000);  // Run for 5 seconds
}
