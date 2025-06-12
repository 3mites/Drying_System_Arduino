#include <SPI.h>
#include <max6675.h>
#include <DHT.h>

// ----- Sensor Pins -----
#define DHTPIN1 30
#define DHTPIN2 31
#define DHTTYPE DHT22
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);

// ----- TCS3200 Pins -----
#define S0 38
#define S1 39
#define S2 40
#define S3 41
#define sensorOut 42
const int NUM_SAMPLES = 5;
unsigned int redFrequency = 0;
unsigned int greenFrequency = 0;
unsigned int blueFrequency = 0;
const int DRY_RED_MIN = 174, DRY_RED_MAX = 180;
const int DRY_GREEN_MIN = 206, DRY_GREEN_MAX = 212;
const int DRY_BLUE_MIN = 180, DRY_BLUE_MAX = 187;

const int testPin = 13;

// Corn Pin
const int cornPin = 9;

// ----- Fan Pins -----
const int Gate1 = 44;
const int Gate2 = 45;
const int Gate3 = 46;

// ----- TRIAC -----
bool triacEnabled = true;
int zeroCross = 3;
int firingAnglePin = 4;
volatile bool doPhaseControl = false;

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
int gate2_pwm = 0;
int gate3_pwm = 0;
int pwm_1 = 0;
int pwm_2 = 0;
int pwmValue = 0;
String speedLabel;
String fanSpeedLabel;

// ----- Control -----
double adjustTemperature = 0.0;
String serialInput = "";
bool newCommand = false;
const float MAX_DIFF = 5.0;  // Max allowed deviation for harmonizing

void harmonizeTemperatures(float* temps, int count) {
  const float CLOSE_THRESHOLD = 2.0;  // Nearby match threshold
  float sum = 0;
  int validCount = 0;

  // Step 1: Calculate average of all valid temps
  for (int i = 0; i < count; i++) {
    if (!isnan(temps[i])) {
      sum += temps[i];
      validCount++;
    }
  }

  if (validCount == 0) return;
  float groupAvg = sum / validCount;

  // Step 2: Identify and replace outliers
  for (int i = 0; i < count; i++) {
    if (isnan(temps[i])) continue;

    float diff = temps[i] - groupAvg;

    if (abs(diff) > MAX_DIFF) {
      // Check if it's close to another reading
      bool closeToOther = false;
      for (int j = 0; j < count; j++) {
        if (i != j && !isnan(temps[j]) && abs(temps[i] - temps[j]) <= CLOSE_THRESHOLD) {
          closeToOther = true;
          break;
        }
      }

      if (!closeToOther) {
        // Recalculate average excluding this outlier
        float partialSum = 0;
        int partialCount = 0;
        for (int k = 0; k < count; k++) {
          if (k != i && !isnan(temps[k]) && abs(temps[k] - groupAvg) <= MAX_DIFF) {
            partialSum += temps[k];
            partialCount++;
          }
        }

        if (partialCount > 0) {
          temps[i] = partialSum / partialCount;
        } else {
          temps[i] = groupAvg; // fallback
        }
      }
    }
  }
}



unsigned int averageColorFrequency(bool s2Val, bool s3Val, int samples) {
  long sum = 0;
  for (int i = 0; i < samples; i++) {
    digitalWrite(S2, s2Val);
    digitalWrite(S3, s3Val);
    // Replace delay with a short timeout-based pulse reading
    unsigned long pulseDuration = pulseIn(sensorOut, LOW, 1000);  // 1000 µs timeout
    if (pulseDuration > 0) {
      sum += pulseDuration;
    } else {
      sum += 1000;  // Use a default fallback if no pulse is read
    }
  }
  return sum / samples;
}


bool isDryCorn(int r, int g, int b) {
  return (r >= DRY_RED_MIN && r <= DRY_RED_MAX) && (g >= DRY_GREEN_MIN && g <= DRY_GREEN_MAX) && (b >= DRY_BLUE_MIN && b <= DRY_BLUE_MAX);
}

void setup() {
  pinMode(testPin, OUTPUT);
  pinMode(Gate1, OUTPUT);
  pinMode(Gate2, OUTPUT);
  pinMode(Gate3, OUTPUT);
  pinMode(zeroCross, INPUT_PULLUP);
  pinMode(firingAnglePin, OUTPUT);
  digitalWrite(firingAnglePin, LOW);
  pinMode(cornPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(zeroCross), zeroCrossDetect, RISING);
  dht1.begin();
  dht2.begin();
  for (int i = 0; i < numSensors; i++) {
    thermocouples_Drying[i] = new MAX6675(thermoCLK, csPins_Drying[i], thermoDO);
    thermocouples_Plenum[i] = new MAX6675(thermoCLK, csPins_Plenum[i], thermoDO);
  }
  pinMode(S0, OUTPUT);
  pinMode(S1, OUTPUT);
  pinMode(S2, OUTPUT);
  pinMode(S3, OUTPUT);
  pinMode(sensorOut, INPUT);
  digitalWrite(S0, HIGH);
  digitalWrite(S1, LOW);
  Serial.begin(9600);
  delay(1000);
}


void phaseControl() {
  float deviation = temperature - 200.0;
  int delayMicros = map(deviation * 10, -100, 100, 1000, 8300);
  delayMicros = constrain(delayMicros, 1000, 8300);
  delayMicroseconds(delayMicros);
  digitalWrite(firingAnglePin, HIGH);
  delayMicroseconds(100);
  digitalWrite(firingAnglePin, LOW);
  if (millis() - lastPhasePrintTime >= printInterval) {
    lastPhasePrintTime = millis();
    Serial.print("TRIAC triggered after delay: ");
    Serial.print(delayMicros);
    Serial.println(" µs");
  }
}

void controlFan() {
  static float prev_h_ave = 0;
  const float hysteresis = 1.0;

  // Fan1: Always ON at medium speed for base circulation
  analogWrite(Gate1, lowPWM);

  if (h_ave > 65.0) {
    // Aggressive Drying
    analogWrite(Gate2, highPWM);
    pwm_1 = highPWM;

    analogWrite(Gate3, mediumPWM);
    pwm_2 = mediumPWM;
    fanSpeedLabel = "HIGH (100%/60%)";

  } else if (h_ave > 50.0 || (prev_h_ave > 50.0 && h_ave > 50.0 - hysteresis)) {
    // Medium Drying
    analogWrite(Gate2, mediumPWM);
    pwm_1 = mediumPWM;

    analogWrite(Gate3, lowPWM);
    pwm_2 = lowPWM;
    fanSpeedLabel = "MEDIUM (60%/20%)";

  } else if (h_ave > 36.0 || (prev_h_ave > 36.0 && h_ave > 36.0 - hysteresis)) {
    // Gentle Drying
    analogWrite(Gate2, lowPWM);
    pwm_1 = lowPWM;

    analogWrite(Gate3, lowPWM);
    pwm_2 = lowPWM;
    fanSpeedLabel = "LOW (20%/20%)";

  } else if (h_ave >= 31.0) {
    // Controlled Final Drying: Fan3 scales from low to medium as RH moves from 36 → 31
    analogWrite(Gate2, 0);
    pwm_1 = 0;

    int pwmFan3 = map(h_ave * 100, 3100, 3600, mediumPWM, lowPWM);  // RH in hundredths
    pwmFan3 = constrain(pwmFan3, lowPWM, mediumPWM);

    analogWrite(Gate3, pwmFan3);
    pwm_2 = pwmFan3;
    fanSpeedLabel = "FINAL DRY (FAN3 scaled)";
  } else {
    // RH goal reached — stop drying
    analogWrite(Gate2, 0);
    pwm_1 = 0;

    analogWrite(Gate3, 0);
    pwm_2 = 0;
    fanSpeedLabel = "OFF";
  }

  // Temperature override — only if RH is above target
  if (h_ave > 36.0 && temperature >= adjustTemperature) {
    int boostPWM = map(temperature, adjustTemperature, adjustTemperature + 10, mediumPWM, highPWM);
    boostPWM = constrain(boostPWM, mediumPWM, highPWM);

    analogWrite(Gate2, boostPWM);
    pwm_1 = boostPWM;

    analogWrite(Gate3, mediumPWM);
    pwm_2 = mediumPWM;
    fanSpeedLabel = "TEMP BOOST";
  }

  prev_h_ave = h_ave;
}


void loop() {
  unsigned long currentMillis = millis();

  // TCS3200 Color Readings
  redFrequency = averageColorFrequency(LOW, LOW, NUM_SAMPLES);
  greenFrequency = averageColorFrequency(HIGH, HIGH, NUM_SAMPLES);
  blueFrequency = averageColorFrequency(LOW, HIGH, NUM_SAMPLES);
  bool dry = isDryCorn(redFrequency, greenFrequency, blueFrequency);

  // Handle Serial Input
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n') newCommand = true;
    else serialInput += inChar;
  }
  if (newCommand) {
    serialInput.trim();
    if (serialInput.startsWith("ADJ")) {
      int sepIndex = serialInput.indexOf('=');
      if (sepIndex != -1 && sepIndex + 1 < serialInput.length()) {
        String valueStr = serialInput.substring(sepIndex + 1);
        double newTemp = valueStr.toFloat();
        if (!isnan(newTemp)) adjustTemperature = newTemp;
      }
    }
    serialInput = "";
    newCommand = false;
  }
  float originalTemps[8];
  for (int i = 0; i < 8; i++) {
    originalTemps[i] = Temperatures[i];
  }

  // Read Thermocouples
  for (int i = 0; i < numSensors; i++) {
    Temperatures[i] = thermocouples_Drying[i]->readCelsius();
    Temperatures[i + 4] = thermocouples_Plenum[i]->readCelsius();
  }
  Serial.println("Temperature pre harmonization");
  for (int i = 0; i < 8; i++) {
    originalTemps[i] = Temperatures[i];
  }
  
  harmonizeTemperatures(Temperatures, 4);
  harmonizeTemperatures(&Temperatures[4], 4);

  Serial.println("Temperature Harmonization:");
  for (int i = 0; i < 8; i++) {
    Serial.print("T");
    Serial.print(i + 1);
    Serial.print(" - Original: ");
    Serial.print(originalTemps[i], 2);
    Serial.print(" | Harmonized: ");
    Serial.println(Temperatures[i], 2);
  }

  float sumDrying = 0, sumPlenum = 0;
  int countDrying = 0, countPlenum = 0;
  for (int i = 0; i < 4; i++) {
    if (!isnan(Temperatures[i])) {
      sumDrying += Temperatures[i];
      countDrying++;
    }
    if (!isnan(Temperatures[i + 4])) {
      sumPlenum += Temperatures[i + 4];
      countPlenum++;
    }
  }

  averageTemp = (countDrying > 0) ? sumDrying / countDrying : NAN;
  averageTemp_Plenum = (countPlenum > 0) ? sumPlenum / countPlenum : NAN;

  if (!isnan(averageTemp)) lastValidAverage = averageTemp;
  else averageTemp = lastValidAverage;
  if (!isnan(averageTemp_Plenum)) lastValidAverage_Plenum = averageTemp_Plenum;
  else averageTemp_Plenum = lastValidAverage_Plenum;

  // Ambient MAX31855
  temperature = thermocouple.readCelsius();
  if (!isnan(temperature)) lastValidTemp = temperature;
  else temperature = lastValidTemp;

  // DHT readings
  if (currentMillis - lastHumidityReadTime >= humidityReadInterval) {
    lastHumidityReadTime = currentMillis;
    float h1 = dht1.readHumidity();
    float h2 = dht2.readHumidity();
    if (!isnan(h1)) H1 = h1;
    if (!isnan(h2)) H2 = h2;
    h_ave = (H1 + H2) / 2.0;
  }

  // Print formatted log
  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;

    //Serial.print("Temperature (MAX31855): ");
    //Serial.println(temperature, 2);

    //Serial.print("Ambient Average Temp: ");
    //Serial.println(averageTemp, 2);

    //pwm_1 = 0;  // Placeholder, update as needed
    //pwm_2 = 0;
    //Serial.print("Fan3 PWM (20%): ");
    //Serial.println(lowPWM);

    //Serial.print("Fan1 PWM: ");
    //Serial.println(pwm_1);

    //Serial.print("Fan1 Speed Label: ");
    //Serial.println(fanSpeedLabel);
    Serial.print("Max31855: ");
    Serial.println(temperature);
    for (int i = 0; i < 8; i++) {
      Serial.print("T");
      Serial.print(i + 1);
      Serial.print(":");
      Serial.print(Temperatures[i], 2);
      Serial.print(" ");
    }
    Serial.print("H1:");
    Serial.print(H1, 2);
    Serial.print(" ");
    Serial.print("H2:");
    Serial.print(H2, 2);
    Serial.print(" ");
    Serial.print("t_ave_first:");
    Serial.print(averageTemp, 2);
    Serial.print(" ");
    Serial.print("t_ave_2nd:");
    Serial.print(averageTemp_Plenum, 2);
    Serial.print(" ");
    Serial.print("h_ave:");
    Serial.print(h_ave, 2);
    Serial.print(" ");
    Serial.print("pwm_1:");
    Serial.print(pwm_1);
    Serial.print(" ");  // Fan2
    Serial.print("pwm_2:");
    Serial.println(pwm_2);  // Fan3

    delay(2000);
    //Serial.print("Corn Dry ");
    //Serial.println(dry ? "✓" : "✘");
  }

  controlFan();

  if (doPhaseControl) {
    doPhaseControl = false;
    phaseControl();
  }
}

void zeroCrossDetect() {
  if (triacEnabled) {
    doPhaseControl = true;
  }
}
