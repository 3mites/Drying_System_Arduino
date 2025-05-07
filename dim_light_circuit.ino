#include "max6675.h"  // Thermocouple library

// Pins for MAX6675
int thermoDO = 50;
int thermoCS = 53;
int thermoCLK = 52;

// TRIAC and zero-cross detection
const byte zeroCrossPin = 3;   // TLP621 output to interrupt
const byte triacPin = 13;      // MOC3021 input gate

MAX6675 thermocouple(thermoCLK, thermoCS, thermoDO);

volatile boolean zeroCrossDetected = false;
bool enableTriac = true;     // Whether TRIAC should be firing
bool triacState = true;      // Current logic state of TRIAC enable

// Temperature control thresholds
const float safeTempMin = 20.0;
const float safeTempMax = 35.0;

int delayTime = 6250;  // µs delay before firing TRIAC
const int MIN_SAFE_DELAY = 150;  // µs to avoid 0 µs firing
const float halfCycleMicroSec = 8333.0;
const float degreesPerMicroSec = 180.0 / halfCycleMicroSec;

void setup() {
  Serial.begin(9600);
  Serial.println("Temperature-based TRIAC Dimmer");

  pinMode(triacPin, OUTPUT);
  digitalWrite(triacPin, LOW);
  pinMode(zeroCrossPin, INPUT);

  attachInterrupt(digitalPinToInterrupt(zeroCrossPin), zeroCrossISR, RISING);

  delay(500);  // Allow thermocouple to stabilize
}

void loop() {
  // Read temperature
  float temperature = thermocouple.readCelsius();

  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println(" °C");

  // Simple hysteresis: TRIAC ON if within range, OFF otherwise
  if (temperature >= safeTempMin && temperature <= safeTempMax) {
    if (!triacState) {
      triacState = true;
      enableTriac = true;
      Serial.println("TRIAC ON (within safe range)");
    }
  } else {
    if (triacState) {
      triacState = false;
      enableTriac = false;
      Serial.println("TRIAC OFF (outside safe range)");
    }
  }

  // Set TRIAC power level (25% mapped to firing delay)
  if (enableTriac) {
    delayTime = getSafeDelay(25);  // 25% power level for demo
    float angle = delayTime * degreesPerMicroSec;
    float powerOut = (angle / 180.0) * 100.0;

    Serial.print("TRIAC Firing - Angle: ");
    Serial.print(angle, 1);
    Serial.print("°, Power Output: ");
    Serial.print(powerOut, 0);
    Serial.println("%");
  }

  loopDimmer();
  delay(1000); // Refresh rate of 1s
}

// Fires TRIAC if zero-cross was detected
void loopDimmer() {
  if (zeroCrossDetected) {
    zeroCrossDetected = false;

    if (enableTriac) {
      delayMicroseconds(delayTime);  // Phase delay
      digitalWrite(triacPin, HIGH);
      delayMicroseconds(100);        // Trigger pulse width
      digitalWrite(triacPin, LOW);
    } else {
      digitalWrite(triacPin, LOW);
    }
  }
}

// Interrupt on zero crossing
void zeroCrossISR() {
  zeroCrossDetected = true;
}

// Converts power level (%) into safe TRIAC delay time (µs)
int getSafeDelay(int percent) {
  return (percent == 0)
    ? MIN_SAFE_DELAY  // Avoid unsafe 0 µs
    : map(percent, 0, 100, MIN_SAFE_DELAY, 8333);
}
