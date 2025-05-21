#include <Adafruit_MAX31855.h>
#include <SPI.h>
#include <max6675.h>

//hysteresis of 250

const int Gate1 = 44;
const int Gate2 = 45;
const int Gate3 = 46;

bool triacEnabled = true;

int zeroCross = 3;       // Zero-crossing detection pin
int firingAnglePin = 4;  // Triac firing angle control pin

unsigned long previousMillis = 0;
const unsigned long interval = 5000;  // 5 seconds per speed step

int pwmValue;
String speedLabel;

const int thermoCLK = 52;  // SCK
const int thermoCS = 53;   // CS
const int thermoDO = 50;   // MISO

const int ambiDO = 9;
const int ambiCS = 10;
const int ambiCLK = 11;

const int maxPWM = 255;

const int ambientReadInterval = 250;       // Read ambient temp every 0.25s
unsigned long lastAmbiReadTime = 0;

const unsigned long printInterval = 2000;  // Print every 2 seconds
unsigned long lastPrintTime = 0;

unsigned long lastPhasePrintTime = 0;      // For phaseControl print throttling

// Speed levels
const int lowPWM = maxPWM * 20 / 100;    // 20%
const int mediumPWM = maxPWM * 60 / 100; // 60%
const int highPWM = maxPWM;              // 100%

double temperature = 0;
double lastValidTemp = 0;
double ambientTemp = 0;
double lastValidAmbient = 0;

volatile bool doPhaseControl = false;
double adjustTemperature = 0;

// Create thermocouple objects
Adafruit_MAX31855 thermocouple(thermoCLK, thermoCS, thermoDO);
MAX6675 ambientSensor(ambiCLK, ambiCS, ambiDO);

void setup() {
  pinMode(Gate1, OUTPUT);
  pinMode(Gate2, OUTPUT);
  pinMode(Gate3, OUTPUT);

  pinMode(zeroCross, INPUT_PULLUP);
  pinMode(firingAnglePin, OUTPUT);
  digitalWrite(firingAnglePin, LOW);

  attachInterrupt(digitalPinToInterrupt(zeroCross), zeroCrossDetect, RISING);

  Serial.begin(9600);
  delay(500);  // Let sensors stabilize
}

void controlFan() {
  // Fan3 always at 20%
  analogWrite(Gate1, lowPWM);

  // Fan1 speed control based on temperature threshold
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    if (temperature >= 100.0) {
      pwmValue = lowPWM;
      speedLabel = "LOW (20%)";
    } else {
      pwmValue = 0;
      speedLabel = "OFF";
    }
  }
  analogWrite(Gate3, pwmValue);
  analogWrite(Gate2, highPWM);
}

void loop() {
  // Read MAX31855 (every loop)
  double tempReading = thermocouple.readCelsius();
  if (!isnan(tempReading)) {
    temperature = tempReading;
    lastValidTemp = tempReading;
  } else {
    temperature = lastValidTemp;
  }

  // Read MAX6675 every 250 ms
  if (millis() - lastAmbiReadTime >= ambientReadInterval) {
    lastAmbiReadTime = millis();

    double ambiReading = ambientSensor.readCelsius();
    if (!isnan(ambiReading) && ambiReading > 0.0 && ambiReading < 1024.0) {
      ambientTemp = ambiReading;
      lastValidAmbient = ambiReading;
    } else {
      ambientTemp = lastValidAmbient;
    }
  }

  // --- TRIAC control based on ambient temperature ---
  if (ambientTemp >= adjustTemperature) {
    if (triacEnabled) {
      Serial.println("TRIAC OFF: Ambient too hot (>80°C)");
    }
    triacEnabled = false;
    doPhaseControl = false;
    digitalWrite(firingAnglePin, LOW);
  } else if (ambientTemp < 30.0) {
    if (!triacEnabled) {
      Serial.println("TRIAC ON: Ambient cooled down (<60°C)");
    }
    triacEnabled = true;
  }

  // Phase control based on MAX31855 temperature to maintain ~200°C
  if (triacEnabled) {
    if (temperature >= 200.0) {
      // Maintain temperature by throttling power with phase control delay
      doPhaseControl = false;
      digitalWrite(firingAnglePin, LOW);
    } else {
      // Heating up: less delay (more power)
      doPhaseControl = true;
    }
  } else {
    // TRIAC disabled: no phase control firing
    doPhaseControl = false;
    digitalWrite(firingAnglePin, LOW);
  }

  controlFan();

  if (doPhaseControl) {
    noInterrupts();
    doPhaseControl = false;
    interrupts();
    phaseControl();
  }

  // Print all info every 2 seconds
  unsigned long currentMillis = millis();
  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;

    Serial.print("Temperature (MAX31855): ");
    Serial.println(temperature);

    Serial.print("Ambient (MAX6675): ");
    Serial.println(ambientTemp);

    Serial.print("Fan3 PWM (constant 20%): ");
    Serial.println(lowPWM);

    Serial.print("Fan1 PWM: ");
    Serial.println(pwmValue);

    Serial.print("Fan1 Speed Label: ");
    Serial.println(speedLabel);
  }
}

void phaseControl() {
  // Calculate deviation from 200°C setpoint
  float deviation = temperature - 200.0;

  // Map deviation to delay for phase angle (microseconds)
  // More positive deviation -> longer delay (less power)
  // More negative deviation -> shorter delay (more power)
  // Limits chosen for 60Hz AC: 1000 - 8300 us delay range
  int delayMicros = map(deviation * 10, -100, 100, 1000, 8300);
  delayMicros = constrain(delayMicros, 1000, 8300);

  delayMicroseconds(delayMicros);

  digitalWrite(firingAnglePin, HIGH);
  delayMicroseconds(100);  // TRIAC gate pulse width
  digitalWrite(firingAnglePin, LOW);

  // Print TRIAC trigger info only every 2 seconds
  unsigned long currentMillis = millis();
  if (currentMillis - lastPhasePrintTime >= printInterval) {
    lastPhasePrintTime = currentMillis;

    Serial.print("TRIAC triggered after delay: ");
    Serial.print(delayMicros);
    Serial.println(" µs");
  }
}

void zeroCrossDetect() {
  if (triacEnabled) {
    doPhaseControl = true;
  }
}