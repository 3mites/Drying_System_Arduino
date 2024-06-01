#include "max6675.h"  //INCLUDE THE LIBRARY

int thermoDO = 9;
int thermoCS = 10;
int thermoCLK = 13;
int PWMfan = 6;
int zeroCross = 8;       // Zero-crossing detection pin
int firingAnglePin = 3;  // Triac firing angle control pin

MAX6675 thermocouple(thermoCLK, thermoCS, thermoDO);
int fanSpeed = 0;              // Initial fan speed
int lastFiringAngleValue = 0;  // Variable to store the last firing angle value

void setup() {
  Serial.begin(9600);
  Serial.println("MAX6675 test");
  // Initialize PWM fan pin
  pinMode(PWMfan, OUTPUT);
  // Initialize zero-crossing detection pin
  pinMode(zeroCross, INPUT_PULLUP);
  // Initialize firing angle control pin
  pinMode(firingAnglePin, OUTPUT);
  // Attach interrupt for zero-crossing detection
  attachInterrupt(digitalPinToInterrupt(zeroCross), zeroCrossDetect, RISING);
  // wait for MAX chip to stabilize
  delay(500);
}

void loop() {
  // Read current temperature
  float temperature = thermocouple.readCelsius();
  // Print the current temperature
  Serial.print("RPM = ");
  Serial.println(fanSpeed);
  Serial.print("C = ");
  Serial.println(temperature);

  // Control fan speed based on temperature
  if (temperature < 40.00) {
    // Set fan speed to maximum
    fanSpeed = 255;
  } else {
    // Turn off the fan
    fanSpeed = 0;
  }
  analogWrite(PWMfan, fanSpeed);
  delay(1000);

  // Call zeroCrossDetect() to adjust firing angle based on temperature
  zeroCrossDetect();

  // Wait for 1 second before checking the temperature again
  //delay(1000);
}

void zeroCrossDetect() {
  // Debug output
  Serial.println("Zero cross detected");

  // Implement phase angle control logic to maintain temperature at 40°C
  float temperature = thermocouple.readCelsius();
  float deviation = temperature - 40.0;  // Calculate deviation from 40°C

  // Debug output
  Serial.print("Temperature deviation: ");
  Serial.println(deviation);

  // Check if temperature exceeds 40°C
  if (temperature >= 40.00) {
    // Turn off the heating element
    analogWrite(firingAnglePin, 0);
    return;  // Exit the function early
  }

  // Proportional control: Map deviation to firing angle (0-180 degrees)
  int firingAngle = map(deviation, -10, 10, 0, 180);

  // Debug output
  Serial.print("Firing angle: ");
  Serial.println(firingAngle);

  // Integral control: Adjust firing angle gradually to avoid sudden changes
  int newFiringAngleValue = map(firingAngle, 0, 180, 0, 255);  // Map firing angle to PWM value

  // Apply hysteresis to avoid frequent changes in the firing angle
  if (abs(newFiringAngleValue - lastFiringAngleValue) >= 5) {
    // Update firing angle value only if the change is significant
    analogWrite(firingAnglePin, newFiringAngleValue);
    lastFiringAngleValue = newFiringAngleValue;

    // Debug output
    Serial.print("New firing angle value: ");
    Serial.println(newFiringAngleValue);
  }
}
