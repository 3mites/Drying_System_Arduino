#include "max6675.h" //INCLUDE THE LIBRARY

int thermoDO = 9;
int thermoCS = 10;
int thermoCLK = 13;
int PWMfan = 6;

MAX6675 thermocouple(thermoCLK, thermoCS, thermoDO);
int fanSpeed = 0; // Initial fan speed

void setup() {
  Serial.begin(9600);
  Serial.println("MAX6675 test");
  // Initialize PWM fan pin
  pinMode(PWMfan, OUTPUT);
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
  if (temperature > 40.00) {
    // Set fan speed to maximum
    fanSpeed = 0;
  } else {
    // Turn off the fan
    fanSpeed = 255;
  }
  analogWrite(PWMfan, fanSpeed);
  delay(1000);

  // Wait for 1 second before checking the temperature again
  //delay(1000);
}
