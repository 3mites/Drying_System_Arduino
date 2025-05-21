#include "max6675.h"

const int thermoDO = 12;
const int thermoCLK = 13;

const int csPins[] = {5, 6, 7, 8, 9};
const int numSensors = sizeof(csPins) / sizeof(csPins[0]);

MAX6675* thermocouples[numSensors];

void setup() {
  Serial.begin(9600);
  Serial.println("MAX6675 Multi-Thermocouple Test");

  for (int i = 0; i < numSensors; i++) {
    thermocouples[i] = new MAX6675(thermoCLK, csPins[i], thermoDO);
  }

  delay(500); 
}

void loop() {
  float temperatures[numSensors];
  float totalTemp = 0;

  for (int i = 0; i < numSensors; i++) {
    temperatures[i] = thermocouples[i]->readCelsius();
    totalTemp += temperatures[i];

    Serial.print("Thermocouple ");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.print(temperatures[i]);
    Serial.print(" °C\t");
  }

  float averageTemp = totalTemp / numSensors;

  Serial.print("\nAverage Temperature: ");
  Serial.print(averageTemp);
  Serial.println(" °C\n");

  delay(1000);
}
