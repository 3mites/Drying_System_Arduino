#include <SPI.h>
#include <max6675.h>
#include <DHT.h>

// ----- Sensor Pins -----
#define DHTPIN1 30
#define DHTPIN2 31
#define SAFETY_BUTTON_PIN 7
#define DHTTYPE DHT22
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);
bool systemHalted = false;
int belowThresholdStart = 0;
volatile int firingDelayMicros = 8500;
unsigned int r, g, b;



// ----- TCS3200 Pins -----
#define S0 38
#define S1 39
#define S2 40
#define S3 41
#define sensorOut 42
#include <TimerOne.h>
const int NUM_SAMPLES = 5;
unsigned int redFrequency = 0;
unsigned int greenFrequency = 0;
unsigned int blueFrequency = 0;
const int DRY_RED_MIN = 174, DRY_RED_MAX = 180;
const int DRY_GREEN_MIN = 206, DRY_GREEN_MAX = 212;
const int DRY_BLUE_MIN = 180, DRY_BLUE_MAX = 187;

// Corn Pin
bool dryAnnounced = false;

const float halfCycleMicroSec = 8333.0;  // 60Hz half-cycle = 8.33ms
const float degreesPerMicroSec = 180.0 / halfCycleMicroSec;  // for phase angle in degrees
// ----- Fan Pins -----
const int Gate1 = 44;
const int Gate2 = 45;
const int Gate3 = 46;

// ----- TRIAC -----
bool triacEnabled = true;
int zeroCross = 3;
int firingAnglePin = 4;
volatile bool doPhaseControl = false;
String desiredAdjustLevel = "";
bool adjustMode = false;
int triacDelay = 8500;

// ----- Timing -----
unsigned long previousMillis = 0;
const unsigned long interval = 5000;
const unsigned long ambientReadInterval = 250;
unsigned long lastAmbiReadTime = 0;
const unsigned long humidityReadInterval = 250;
unsigned long lastHumidityReadTime = 0;
const unsigned long printInterval = 2000;
unsigned long lastPrintTime = 0;
unsigned long lastPhasePrintTime = 0;

// ----- MAX31855 -----
const int thermo6675CLK = 11;
const int thermo6675DO = 12;
const int thermo6675CS = 13;
MAX6675 thermocouple(thermo6675CLK, thermo6675CS, thermo6675DO);
double temperature = 0;
double lastValidTemp = 0;

// ----- MAX6675 -----
const int thermoCLK = 52;
const int thermoDO = 50;
const int numSensors = 4;
const int csPins_Drying[] = { 22, 23, 24, 25 };
const int csPins_Plenum[] = { 26, 27, 28, 29 };
MAX6675* thermocouples_Drying[numSensors];
MAX6675* thermocouples_Plenum[numSensors];
float Temperatures[8];
float averageTemp = 0;
float lastValidAverage = 0;
float averageTemp_Plenum = 0;
float lastValidAverage_Plenum = 0;

// ----- Humidity -----
float H1 = NAN;
float H2 = NAN;
float h_ave = 0.0;

// ----- Fan Speed -----
const int maxPWM = 255;
const int lowPWM = maxPWM * 20 / 100;
const int mediumPWM = maxPWM * 60 / 100;
const int highPWM = maxPWM;
int pwm_1 = 0;
int pwm_2 = 0;
String fanSpeedLabel;
bool adjustmentEnabled = false;

// ----- Control -----
String serialInput = "";
bool newCommand = false;
const float MAX_DIFF = 5.0;

float adjustTemperature = 0.00;

void getRGB(unsigned int &r, unsigned int &g, unsigned int &b) {
  r = averageColorFrequency(LOW, LOW, NUM_SAMPLES);
  g = averageColorFrequency(HIGH, HIGH, NUM_SAMPLES);
  b = averageColorFrequency(LOW, HIGH, NUM_SAMPLES);
}

int getPowerFromAdjust(float adjVal) {
  if (adjVal >= 25.0 && adjVal < 36.0) return 25;   // Low heating
  if (adjVal >= 34.0 && adjVal < 60.0) return 50;   // Medium heating
  if (adjVal >= 55.0 && adjVal <= 73.0) return 75;  // High heating
  return 0;  // Outside range → no heating
}

void harmonizeTemperatures(float* temps, int count) {
  const float CLOSE_THRESHOLD = 2.0;
  float sum = 0;
  int validCount = 0;

  for (int i = 0; i < count; i++) {
    if (!isnan(temps[i])) {
      sum += temps[i];
      validCount++;
    }
  }

  if (validCount == 0) return;
  float groupAvg = sum / validCount;

  for (int i = 0; i < count; i++) {
    if (isnan(temps[i])) continue;
    float diff = temps[i] - groupAvg;
    if (abs(diff) > MAX_DIFF) {
      bool closeToOther = false;
      for (int j = 0; j < count; j++) {
        if (i != j && !isnan(temps[j]) && abs(temps[i] - temps[j]) <= CLOSE_THRESHOLD) {
          closeToOther = true;
          break;
        }
      }
      if (!closeToOther) {
        float partialSum = 0;
        int partialCount = 0;
        for (int k = 0; k < count; k++) {
          if (k != i && !isnan(temps[k]) && abs(temps[k] - groupAvg) <= MAX_DIFF) {
            partialSum += temps[k];
            partialCount++;
          }
        }
        temps[i] = (partialCount > 0) ? (partialSum / partialCount) : groupAvg;
      }
    }
  }
}


unsigned int averageColorFrequency(bool s2Val, bool s3Val, int samples) {
  digitalWrite(S2, s2Val);
  digitalWrite(S3, s3Val);
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    unsigned long pulseDuration = pulseIn(sensorOut, LOW, 1000);
    sum += (pulseDuration > 0) ? pulseDuration : 1000;
  }
  return sum / samples;
}

bool isDryCorn(int r, int g, int b) {
  return (r >= DRY_RED_MIN && r <= DRY_RED_MAX) &&
         (g >= DRY_GREEN_MIN && g <= DRY_GREEN_MAX) &&
         (b >= DRY_BLUE_MIN && b <= DRY_BLUE_MAX);
}

bool isConsistentlyDry() {
  int dryCount = 0;
  for (int i = 0; i < 3; i++) {
    int r = averageColorFrequency(LOW, LOW, NUM_SAMPLES);
    int g = averageColorFrequency(HIGH, HIGH, NUM_SAMPLES);
    int b = averageColorFrequency(LOW, HIGH, NUM_SAMPLES);

    if (isDryCorn(r, g, b)) dryCount++;
    delay(200);  // Short pause between checks
  }
  return (dryCount >= 3);  // Require 3/3 consistent dry readings
}

void setup() {
  pinMode(SAFETY_BUTTON_PIN, INPUT_PULLUP);  // Use internal pull-up
  Serial.begin(115200);
  Serial.println("Waiting for all buttons to be pressed...");

  // Wait until pin 7 goes LOW (if using pull-up logic)
  while (digitalRead(SAFETY_BUTTON_PIN) == HIGH) {
    delay(100);
    Serial.println("Waiting...");
  }

  Serial.println("All buttons pressed. Proceeding...");
  pinMode(Gate1, OUTPUT);
  pinMode(Gate2, OUTPUT);
  pinMode(Gate3, OUTPUT);
  pinMode(zeroCross, INPUT_PULLUP);
  pinMode(firingAnglePin, OUTPUT);
  digitalWrite(firingAnglePin, LOW);
  attachInterrupt(digitalPinToInterrupt(zeroCross), zeroCrossDetect, RISING);
  dht1.begin();
  dht2.begin();
  for (int i = 0; i < numSensors; i++) {
    thermocouples_Drying[i] = new MAX6675(thermoCLK, csPins_Drying[i], thermoDO);
    thermocouples_Plenum[i] = new MAX6675(thermoCLK, csPins_Plenum[i], thermoDO);
  }
  pinMode(S0, OUTPUT); pinMode(S1, OUTPUT); pinMode(S2, OUTPUT); pinMode(S3, OUTPUT);
  pinMode(sensorOut, INPUT);
  digitalWrite(S0, HIGH);
  digitalWrite(S1, LOW);
  Serial.begin(115200);
  delay(1000);
}

int powerPercent = 0; // Example: 75% dimming = less power

void zeroCrossDetect() {
  if (triacEnabled) {
    Timer1.stop();
    Timer1.initialize(firingDelayMicros); // Wait this many µs after ZC
    Timer1.attachInterrupt(fireTriac);
  }
}

void fireTriac() {
  int delayTime = map(powerPercent, 0, 100, 0, 8333);
  digitalWrite(firingAnglePin, HIGH);
  delayMicroseconds(100);
  digitalWrite(firingAnglePin, LOW);
}


void controlFan() {
  // Gate1 always at lowPWM
  analogWrite(Gate1, lowPWM);

  if (h_ave >= 55.0) {
    analogWrite(Gate2, mediumPWM-50);   // Gate2 = 100%
    analogWrite(Gate3, lowPWM);    // Gate3 = 20%
    pwm_1 = mediumPWM;
    pwm_2 = lowPWM;
    fanSpeedLabel = "RH >= 40 → Gate2 = 100%, Gate3 = 20%";
  } else if (h_ave >= 30.0) {
    analogWrite(Gate2, 0);    // Gate2 = 20%on
    analogWrite(Gate3, 95); // Gate3 = 60%
    pwm_1 = 0;
    pwm_2 = 95;
    fanSpeedLabel = "30 <= RH < 40 → Gate2 = 20%, Gate3 = 60%";
  } else {
    analogWrite(Gate2, 0);
    analogWrite(Gate3, 95); // Gate3 = 60%
    pwm_1 = 0;
    pwm_2 = 95;
    fanSpeedLabel = "RH < 30 → Gate2 = 20%, Gate3 = 60%";
  }
}


void loop() {

  if (digitalRead(SAFETY_BUTTON_PIN) == HIGH) {
    Serial.println("Button released! Halting system...");
    systemHalted = true;
    return;
  }
  
  if (systemHalted) {
    return;  // Skip everything else
  }
  
  unsigned long currentMillis = millis();
  if (!dryAnnounced && isConsistentlyDry()) {
    Serial.println("DRY");
    dryAnnounced = true;
    systemHalted = true;
  }

  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') newCommand = true;
    else serialInput += inChar;
  }

  if (newCommand && adjustmentEnabled) {  // Only allow ADJ when ready
    serialInput.trim();
    if (serialInput.startsWith("ADJ=")) {
      String valueStr = serialInput.substring(4);
      float newVal = valueStr.toFloat();
      if (newVal >= 0.0 && newVal <= 100.0) {
        adjustTemperature = newVal;
        Serial.print("New adjust temperature set to: ");
        Serial.println(adjustTemperature);
      } else {
        Serial.println("Invalid ADJ value. Must be between 0.0 and 100.0");
      }
    }
    serialInput = "";
    newCommand = false;
  }

  for (int i = 0; i < numSensors; i++) {
    Temperatures[i] = thermocouples_Drying[i]->readCelsius();
    Temperatures[i + 4] = thermocouples_Plenum[i]->readCelsius();
  }

  float originalTemps[8];
  for (int i = 0; i < 8; i++) originalTemps[i] = Temperatures[i];

  harmonizeTemperatures(Temperatures, 4);
  harmonizeTemperatures(&Temperatures[4], 4);

  float sumDrying = 0, sumPlenum = 0;
  int countDrying = 0, countPlenum = 0;
  for (int i = 0; i < 4; i++) {
    if (!isnan(Temperatures[i])) { sumDrying += Temperatures[i]; countDrying++; }
    if (!isnan(Temperatures[i + 4])) { sumPlenum += Temperatures[i + 4]; countPlenum++; }
  }
  averageTemp = (countDrying > 0) ? sumDrying / countDrying : lastValidAverage;
  averageTemp_Plenum = (countPlenum > 0) ? sumPlenum / countPlenum : lastValidAverage_Plenum;
  lastValidAverage = averageTemp;
  lastValidAverage_Plenum = averageTemp_Plenum;

  temperature = thermocouple.readCelsius();
  if (!isnan(temperature)) lastValidTemp = temperature;
  else temperature = lastValidTemp;

    // --- TRIAC Control Power Adjustment ---
  if (h_ave >= 53.0) {
    powerPercent = 25;  // High humidity triggers heating
  } else {
    if (averageTemp >= adjustTemperature) {
      powerPercent = 75;  // Turn off heating
    } else {
      powerPercent = 25; // Maintain 75% power if under target
    }
  }

    // Check if adjustment logic can now be used
  static bool adjustmentReadyAnnounced = false;
  if (!adjustmentEnabled) {
    if (h_ave < 31.0) {
      // Stay in full power mode
      powerPercent = 25;
      if (!triacEnabled) Serial.println("TRIAC FORCED ON: RH < 31%");
      triacEnabled = true;
      doPhaseControl = true;

      // If humidity has been low for long enough, enable adjustment
      static unsigned long belowThresholdStart = 0;
      if (belowThresholdStart == 0) belowThresholdStart = millis();
      if (millis() - belowThresholdStart > 15000) {  // 15 seconds of low humidity
        adjustmentEnabled = true;
        if (!adjustmentReadyAnnounced) {
          Serial.println("Humidity < 31% for 15 sec — switching to ADJ control.");
          adjustmentReadyAnnounced = true;
        }
      }
    } else {
      // Reset timer if humidity went back up
      belowThresholdStart = 0;
    }
  }

  // Determine TRIAC power based on whether we're ignoring or allowing adjustment
  if (!adjustmentEnabled) {
    powerPercent = 25;
    triacEnabled = true;
    doPhaseControl = true;
  } else {
    if (h_ave >= 53.0) {
      powerPercent = 25;
      triacEnabled = true;
      doPhaseControl = true;
    } else if (averageTemp >= adjustTemperature) {
      powerPercent = 100; // No power
      triacEnabled = false;
      doPhaseControl = false;
      digitalWrite(firingAnglePin, LOW);
    } else {
      powerPercent = getPowerFromAdjust(adjustTemperature);
      triacEnabled = (powerPercent > 0);
      doPhaseControl = triacEnabled;
      if (!doPhaseControl) digitalWrite(firingAnglePin, LOW);
    }
  }

    // Final safety
  if (!triacEnabled) {
      doPhaseControl = false;
      digitalWrite(firingAnglePin, LOW);
  }


  if (currentMillis - lastHumidityReadTime >= humidityReadInterval) {
    lastHumidityReadTime = currentMillis;
    float h1 = dht1.readHumidity();
    float h2 = dht2.readHumidity();
    if (!isnan(h1)) H1 = h1;
    if (!isnan(h2)) H2 = h2;
    if (!isnan(H1) && !isnan(H2)) h_ave = (H1 + H2) / 2.0;
    else if (!isnan(H1)) h_ave = H1;
    else if (!isnan(H2)) h_ave = H2;
  }

  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;
    getRGB(r, g, b);
    Serial.print("RGB=");
    Serial.print(r); Serial.print(",");
    Serial.print(g); Serial.print(",");
    Serial.println(b);
    Serial.println(dryAnnounced ? "Dry corn detected!" : "Not dry yet.");
    Serial.print("Max31855: ");
    Serial.println(temperature);
    for (int i = 0; i < 8; i++) {
      Serial.print("T"); Serial.print(i + 1); Serial.print(":"); Serial.print(Temperatures[i], 2); Serial.print(" ");
    }
    Serial.print("H1:"); Serial.print(H1, 2); Serial.print(" ");
    Serial.print("H2:"); Serial.print(H2, 2); Serial.print(" ");
    Serial.print("t_ave_first:"); Serial.print(averageTemp, 2); Serial.print(" ");
    Serial.print("t_ave_2nd:"); Serial.print(averageTemp_Plenum, 2); Serial.print(" ");
    Serial.print("h_ave:"); Serial.print(h_ave, 2); Serial.print(" ");
    Serial.print("pwm_1:"); Serial.print(pwm_1); Serial.print(" ");
    Serial.print("pwm_2:"); Serial.println(pwm_2);
    delay(2000);  // previously 2000, now faster
  }

  controlFan();
  if (doPhaseControl) {
    doPhaseControl = false;
    Serial.println("TRIAC phase control triggered"); 
  }
}



