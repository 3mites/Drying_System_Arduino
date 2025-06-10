#include <Adafruit_MAX31855.h>
#include <SPI.h>
#include <max6675.h>
#include <DHT.h>

// ----- Sensor Pins -----
#define DHTPIN1 30
#define DHTPIN2 31
#define DHTTYPE DHT22
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);

// Corn Sensor (TCS3200)
#define S0 38
#define S1 39
#define S2 40
#define S3 41
#define sensorOut 42
const int cornPin = 9;

// Fan Pins
const int Gate1 = 44;
const int Gate2 = 45;
const int Gate3 = 46;

// TRIAC
bool triacEnabled = true;
int zeroCross = 3;
int firingAnglePin = 4;
volatile bool doPhaseControl = false;

// Timing
unsigned long previousMillis = 0;
const unsigned long interval = 5000;
const unsigned long ambientReadInterval = 250;
unsigned long lastAmbiReadTime = 0;
const unsigned long humidityReadInterval = 250;
unsigned long lastHumidityReadTime = 0;
const unsigned long printInterval = 2000;
unsigned long lastPrintTime = 0;
unsigned long lastPhasePrintTime = 0;
unsigned long lastCornCheck = 0;
const unsigned long cornCheckInterval = 900000;

// MAX31855
const int thermo31855CLK = 11;
const int thermo31855DO = 12;
const int thermo31855CS = 53;
Adafruit_MAX31855 thermocouple(thermo31855CLK, thermo31855CS, thermo31855DO);
double temperature = 0;
double lastValidTemp = 0;

// MAX6675
const int thermoCLK = 52;
const int thermoDO = 50;
const int numSensors = 4;
const int csPins_Drying[] = {22, 23, 24, 25};
const int csPins_Plenum[] = {26, 27, 28, 29};
MAX6675* thermocouples_Drying[numSensors];
MAX6675* thermocouples_Plenum[numSensors];
float Temperatures[8];
float averageTemp = 0;
float lastValidAverage = 0;
float averageTemp_Plenum = 0;
float lastValidAverage_Plenum = 0;

// Humidity
float H1 = NAN;
float H2 = NAN;
float h_ave = 0.0;

// Fan Speed
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

// Control
double adjustTemperature = 0.0;
String serialInput = "";
bool newCommand = false;
const float MAX_DIFF = 5.0;

// TCS3200 moving average
const int AVG_WINDOW = 10;
int redValues[AVG_WINDOW] = {0}, greenValues[AVG_WINDOW] = {0}, blueValues[AVG_WINDOW] = {0};

const int DRY_RED_MIN = 174, DRY_RED_MAX = 180;
const int DRY_GREEN_MIN = 206, DRY_GREEN_MAX = 212;
const int DRY_BLUE_MIN = 180, DRY_BLUE_MAX = 187;

void harmonizeTemperatures(float* temps, int count) {
  float sum = 0;
  int validCount = 0;
  for (int i = 0; i < count; i++) {
    if (!isnan(temps[i])) {
      sum += temps[i];
      validCount++;
    }
  }
  if (validCount == 0) return;
  float avg = sum / validCount;
  for (int i = 0; i < count; i++) {
    if (!isnan(temps[i]) && abs(temps[i] - avg) > MAX_DIFF) {
      temps[i] = avg;
    }
  }
}

unsigned int readColorFrequency(bool s2Val, bool s3Val) {
  digitalWrite(S2, s2Val);
  digitalWrite(S3, s3Val);
  delay(100);
  return pulseIn(sensorOut, LOW);
}

bool isDryCorn(int r, int g, int b) {
  return (r >= DRY_RED_MIN && r <= DRY_RED_MAX) &&
         (g >= DRY_GREEN_MIN && g <= DRY_GREEN_MAX) &&
         (b >= DRY_BLUE_MIN && b <= DRY_BLUE_MAX);
}

void setup() {
  pinMode(Gate1, OUTPUT);
  pinMode(Gate2, OUTPUT);
  pinMode(Gate3, OUTPUT);
  pinMode(zeroCross, INPUT_PULLUP);
  pinMode(firingAnglePin, OUTPUT);
  digitalWrite(firingAnglePin, LOW);
  pinMode(cornPin, INPUT_PULLUP);

  pinMode(S0, OUTPUT);
  pinMode(S1, OUTPUT);
  pinMode(S2, OUTPUT);
  pinMode(S3, OUTPUT);
  pinMode(sensorOut, INPUT);
  digitalWrite(S0, HIGH);
  digitalWrite(S1, LOW);

  attachInterrupt(digitalPinToInterrupt(zeroCross), zeroCrossDetect, RISING);
  dht1.begin(); dht2.begin();

  for (int i = 0; i < numSensors; i++) {
    thermocouples_Drying[i] = new MAX6675(thermoCLK, csPins_Drying[i], thermoDO);
    thermocouples_Plenum[i] = new MAX6675(thermoCLK, csPins_Plenum[i], thermoDO);
  }

  Serial.begin(9600);
  delay(500);
}

void loop() {
  unsigned long currentMillis = millis();

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
        double newTemp = serialInput.substring(sepIndex + 1).toFloat();
        if (!isnan(newTemp)) adjustTemperature = newTemp;
      }
    }
    serialInput = "";
    newCommand = false;
  }

  if (currentMillis - lastHumidityReadTime >= humidityReadInterval) {
    lastHumidityReadTime = currentMillis;
    float h1 = dht1.readHumidity();
    float h2 = dht2.readHumidity();
    if (!isnan(h1) && h1 >= 0 && h1 <= 100) H1 = h1;
    if (!isnan(h2) && h2 >= 0 && h2 <= 100) H2 = h2;
    h_ave = (!isnan(H1) && !isnan(H2)) ? (H1 + H2) / 2 : (!isnan(H1) ? H1 : H2);
  }

  if (currentMillis - lastAmbiReadTime >= ambientReadInterval) {
    lastAmbiReadTime = currentMillis;
    float totalTemp_Drying = 0, totalTemp_Plenum = 0;
    int validCount_Drying = 0, validCount_Plenum = 0;
    for (int i = 0; i < numSensors; i++) {
      float tempDrying = thermocouples_Drying[i]->readCelsius();
      Temperatures[i + 4] = (!isnan(tempDrying) && tempDrying > 0 && tempDrying < 1024.0) ? tempDrying : NAN;
      if (!isnan(Temperatures[i + 4])) totalTemp_Drying += Temperatures[i + 4], validCount_Drying++;

      float tempPlenum = thermocouples_Plenum[i]->readCelsius();
      Temperatures[i] = (!isnan(tempPlenum) && tempPlenum > 0 && tempPlenum < 1024.0) ? tempPlenum : NAN;
      if (!isnan(Temperatures[i])) totalTemp_Plenum += Temperatures[i], validCount_Plenum++;
    }
    harmonizeTemperatures(Temperatures, 8);
    averageTemp = validCount_Drying > 0 ? totalTemp_Drying / validCount_Drying : lastValidAverage;
    lastValidAverage = averageTemp;
    averageTemp_Plenum = validCount_Plenum > 0 ? totalTemp_Plenum / validCount_Plenum : lastValidAverage_Plenum;
    lastValidAverage_Plenum = averageTemp_Plenum;
  }

  double tempReading = thermocouple.readCelsius();
  temperature = !isnan(tempReading) ? tempReading : lastValidTemp;
  lastValidTemp = temperature;

  if (averageTemp >= adjustTemperature) {
    if (triacEnabled) Serial.println("TRIAC OFF: Ambient too hot");
    triacEnabled = false;
    doPhaseControl = false;
    digitalWrite(firingAnglePin, LOW);
  } else {
    if (!triacEnabled) Serial.println("TRIAC ON: Ambient cooled down");
    triacEnabled = true;
  }

  if (triacEnabled) {
    doPhaseControl = (temperature < 200.0);
    if (!doPhaseControl) digitalWrite(firingAnglePin, LOW);
  } else {
    digitalWrite(firingAnglePin, LOW);
  }

  analogWrite(Gate1, mediumPWM);
  if (h_ave >= 50.0 && h_ave <= 60.0) {
    gate2_pwm = highPWM;
    gate3_pwm = highPWM;
  } else {
    gate2_pwm = 0;
    gate3_pwm = lowPWM;
  }
  analogWrite(Gate2, gate2_pwm);
  analogWrite(Gate3, gate3_pwm);

  if (doPhaseControl) {
    noInterrupts();
    doPhaseControl = false;
    interrupts();
    phaseControl();
  }

  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;
    Serial.print("Temp31855: "); Serial.println(temperature);
    Serial.print("AmbientAvg: "); Serial.println(averageTemp);
  }

  if (currentMillis - lastCornCheck >= cornCheckInterval) {
    lastCornCheck = currentMillis;
    int rSum = 0, gSum = 0, bSum = 0;
    for (int i = 0; i < AVG_WINDOW; i++) {
      redValues[i] = readColorFrequency(LOW, LOW);
      greenValues[i] = readColorFrequency(HIGH, HIGH);
      blueValues[i] = readColorFrequency(LOW, HIGH);
      delay(50);
    }
    for (int i = 0; i < AVG_WINDOW; i++) {
      rSum += redValues[i]; gSum += greenValues[i]; bSum += blueValues[i];
    }
    int avgRed = rSum / AVG_WINDOW;
    int avgGreen = gSum / AVG_WINDOW;
    int avgBlue = bSum / AVG_WINDOW;

    Serial.print("Avg R: "); Serial.print(avgRed);
    Serial.print(" G: "); Serial.print(avgGreen);
    Serial.print(" B: "); Serial.println(avgBlue);
    if (isDryCorn(avgRed, avgGreen, avgBlue)) Serial.println("✔ Corn is DRY");
    else Serial.println("✘ Corn is NOT dry enough");
  }
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
    Serial.print("TRIAC delay: "); Serial.print(delayMicros); Serial.println(" us");
  }
}

void zeroCrossDetect() {
  if (triacEnabled) doPhaseControl = true;
}
