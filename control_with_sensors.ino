#include <Adafruit_MAX31855.h>
#include <SPI.h>
#include <max6675.h>
#include <DHT.h>

#define DHTPIN1 2  // First DHT22 sensor connected to pin 2
#define DHTPIN2 3  // Second DHT22 sensor connected to pin 3

#define DHTTYPE DHT22

DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);

// Define pins and constants
const int Gate1 = 44;
const int Gate2 = 45;
const int Gate3 = 46;

bool triacEnabled = true;

int zeroCross = 3;
int firingAnglePin = 4;

unsigned long previousMillis = 0;
const unsigned long interval = 5000;
const unsigned long ambientReadInterval = 250;
unsigned long lastAmbiReadTime = 0;
const unsigned long printInterval = 2000;
unsigned long lastPrintTime = 0;
unsigned long lastPhasePrintTime = 0;

const int thermoCLK = 52;
const int thermoCS = 53;
const int thermoDO = 50;

const int maxPWM = 255;
const int lowPWM = maxPWM * 20 / 100;
const int mediumPWM = maxPWM * 60 / 100;
const int highPWM = maxPWM;

double temperature = 0;
double lastValidTemp = 0;
float averageTemp = 0;  // Used instead of ambientTemp
float lastValidAverage = 0;
float averageTemp_Plenum = 0;
float lastValidAverage_Plenum = 0;

int gate2_pwm = 0;
int gate3_pwm = 0;

String speedLabel;
String fanSpeedLabel;

volatile bool doPhaseControl = false;
double adjustTemperature = 80.0; // Example threshold

// For multi-sensor averaging
const int csPins_Drying[] = {5, 6, 7, 8};
const int csPins_Plenum[] = {9, 10, 11, 12};

const int numSensors = 4;

MAX6675* thermocouples_Drying[numSensors];
MAX6675* thermocouples_Plenum[numSensors];

float Temperatures[8];

float h_ave = 0.0;

unsigned long lastHumidityReadTime = 0;
const unsigned long humidityReadInterval = 250;

float H1 = NAN;
float H2 = NAN;

int pwm_1 = 0;
int pwm_2 = 0;
int pwmValue = 0;

Adafruit_MAX31855 thermocouple(thermoCLK, thermoCS, thermoDO);

void setup() {
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

  Serial.begin(9600);
  delay(500); // Stabilize sensors
}

void controlFan() {
  analogWrite(Gate1, lowPWM); // Fan3 always at 20%

  if (h_ave >= 50.0 && h_ave <= 60.0) {
    gate2_pwm = highPWM;       // Store current PWM for Gate2
    gate3_pwm = mediumPWM;     // Store current PWM for Gate3
  } else if (h_ave >= 30.0 && h_ave <= 40.0) {
    gate2_pwm = 0;
    gate3_pwm = lowPWM;
  } else {
    gate2_pwm = 0;
    gate3_pwm = 0;
  }

  analogWrite(Gate2, gate2_pwm);
  analogWrite(Gate3, gate3_pwm);

  // Update fan speed label accordingly
  if (gate2_pwm == highPWM && gate3_pwm == mediumPWM) {
    fanSpeedLabel = "HIGH/MEDIUM";
  } else if (gate2_pwm == 0 && gate3_pwm == lowPWM) {
    fanSpeedLabel = "OFF/LOW";
  } else if (gate2_pwm == 0 && gate3_pwm == 0) {
    fanSpeedLabel = "OFF";
  } else {
    fanSpeedLabel = "CUSTOM";
  }
}

void loop() {
  unsigned long currentMillis = millis();

  // Read humidity values from DHT sensors periodically
  if (currentMillis - lastHumidityReadTime >= humidityReadInterval) {
    lastHumidityReadTime = currentMillis;

    float h1 = dht1.readHumidity();
    float h2 = dht2.readHumidity();

    // Validate readings, ignore NAN or invalid
    if (!isnan(h1) && h1 >= 0 && h1 <= 100) H1 = h1;
    if (!isnan(h2) && h2 >= 0 && h2 <= 100) H2 = h2;

    // Average humidity (h_ave)
    if (!isnan(H1) && !isnan(H2)) {
      h_ave = (H1 + H2) / 2.0;
    } else if (!isnan(H1)) {
      h_ave = H1;
    } else if (!isnan(H2)) {
      h_ave = H2;
    }
  }

  if (currentMillis - lastAmbiReadTime >= ambientReadInterval) {
    lastAmbiReadTime = currentMillis;

    float totalTemp_Drying = 0;
    int validCount_Drying = 0;
    float totalTemp_Plenum = 0;
    int validCount_Plenum = 0;

    for (int i = 0; i < numSensors; i++) {
      float tempDrying = thermocouples_Drying[i]->readCelsius();
      if (!isnan(tempDrying) && tempDrying > 0 && tempDrying < 1024.0) {
        Temperatures[i + 4] = tempDrying;
        totalTemp_Drying += tempDrying;
        validCount_Drying++;
      } else {
        Temperatures[i + 4] = NAN;
      }

      float tempPlenum = thermocouples_Plenum[i]->readCelsius();
      if (!isnan(tempPlenum) && tempPlenum > 0 && tempPlenum < 1024.0) {
        Temperatures[i] = tempPlenum;
        totalTemp_Plenum += tempPlenum;
        validCount_Plenum++;
      } else {
        Temperatures[i] = NAN;
      }
    }

    averageTemp = validCount_Drying > 0 ? totalTemp_Drying / validCount_Drying : lastValidAverage;
    lastValidAverage = averageTemp;

    averageTemp_Plenum = validCount_Plenum > 0 ? totalTemp_Plenum / validCount_Plenum : lastValidAverage_Plenum;
    lastValidAverage_Plenum = averageTemp_Plenum;
  }

  double tempReading = thermocouple.readCelsius();
  if (!isnan(tempReading)) {
    temperature = tempReading;
    lastValidTemp = tempReading;
  } else {
    temperature = lastValidTemp;
  }

  if (averageTemp >= adjustTemperature) {
    if (triacEnabled) Serial.println("TRIAC OFF: Ambient too hot");
    triacEnabled = false;
    doPhaseControl = false;
    digitalWrite(firingAnglePin, LOW);
  } else if (averageTemp < adjustTemperature) {
    if (!triacEnabled) Serial.println("TRIAC ON: Ambient cooled down");
    triacEnabled = true;
  }

  if (triacEnabled) {
    doPhaseControl = (temperature < 200.0);
    if (!doPhaseControl) digitalWrite(firingAnglePin, LOW);
  } else {
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

  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;

    Serial.print("Temperature (MAX31855): "); Serial.println(temperature);
    Serial.print("Ambient Average Temp: "); Serial.println(averageTemp);
    Serial.print("Fan3 PWM (20%): "); Serial.println(lowPWM);
    Serial.print("Fan1 PWM: "); Serial.println(pwmValue);
    Serial.print("Fan1 Speed Label: "); Serial.println(speedLabel);

    Serial.print("T1:"); Serial.print(Temperatures[0], 2); Serial.print(" ");
    Serial.print("T2:"); Serial.print(Temperatures[1], 2); Serial.print(" ");
    Serial.print("T3:"); Serial.print(Temperatures[2], 2); Serial.print(" ");
    Serial.print("T4:"); Serial.print(Temperatures[3], 2); Serial.print(" ");

    Serial.print("T5:"); Serial.print(Temperatures[4], 2); Serial.print(" ");
    Serial.print("T6:"); Serial.print(Temperatures[5], 2); Serial.print(" ");
    Serial.print("T7:"); Serial.print(Temperatures[6], 2); Serial.print(" ");
    Serial.print("T8:"); Serial.print(Temperatures[7], 2); Serial.print(" ");

    Serial.print("H1:"); Serial.print(H1, 2); Serial.print(" ");
    Serial.print("H2:"); Serial.print(H2, 2); Serial.print(" ");
    Serial.print("t_ave_first:"); Serial.print(averageTemp, 2); Serial.print(" ");
    Serial.print("t_ave_2nd:"); Serial.print(averageTemp_Plenum, 2); Serial.print(" ");
    Serial.print("h_ave:"); Serial.print(h_ave, 2); Serial.print(" ");
    Serial.print("pwm_1:"); Serial.print(pwm_1); Serial.print(" ");
    Serial.print("pwm_2:"); Serial.println(pwm_2);
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
    Serial.print("TRIAC triggered after delay: ");
    Serial.print(delayMicros); Serial.println(" µs");
  }
}

void zeroCrossDetect() {
  if (triacEnabled) {
    doPhaseControl = true;
  }
}
