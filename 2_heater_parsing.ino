#include <Adafruit_MAX31855.h>
#include <SPI.h>
#include <max6675.h>
#include <DHT.h>

// ----- Sensor Pins -----
#define DHTPIN1 2
#define DHTPIN2 3
#define DHTTYPE DHT22
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);

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
const int thermoCLK = 52;
const int thermoCS = 53;
const int thermoDO = 50;
Adafruit_MAX31855 thermocouple(thermoCLK, thermoCS, thermoDO);
double temperature = 0;
double lastValidTemp = 0;

// ----- MAX6675 -----
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
double adjustTemperature = 80.0;

String serialInput = "";
bool newCommand = false;

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
  delay(500);
}

void loop() {
  unsigned long currentMillis = millis();
  
  while (Serial.available()) {
    char inChar = (char)Serial.read();

    if (inChar == '\n') {
      newCommand = true;
    } else {
      serialInput += inChar;
    }
  }

  if (newCommand) {
    serialInput.trim();

    if (serialInput.startsWith("ADJ")) {
      int sepIndex = serialInput.indexOf('=');
      if (sepIndex != -1 && sepIndex + 1 < serialInput.length()) {
        String valueStr = serialInput.substring(sepIndex + 1);
        double newTemp = valueStr.toFloat();

        if (!isnan(newTemp)) {
          adjustTemperature = newTemp;
        }
      }
    }

    serialInput = "";
    newCommand = false;
  }

  // --- Read humidity ---
  if (currentMillis - lastHumidityReadTime >= humidityReadInterval) {
    lastHumidityReadTime = currentMillis;
    float h1 = dht1.readHumidity();
    float h2 = dht2.readHumidity();

    if (!isnan(h1) && h1 >= 0 && h1 <= 100) H1 = h1;
    if (!isnan(h2) && h2 >= 0 && h2 <= 100) H2 = h2;

    if (!isnan(H1) && !isnan(H2)) {
      h_ave = (H1 + H2) / 2.0;
    } else if (!isnan(H1)) {
      h_ave = H1;
    } else if (!isnan(H2)) {
      h_ave = H2;
    }
  }

  // --- Read ambient thermocouples ---
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

  // --- Read MAX31855 ---
  double tempReading = thermocouple.readCelsius();
  if (!isnan(tempReading)) {
    temperature = tempReading;
    lastValidTemp = tempReading;
  } else {
    temperature = lastValidTemp;
  }

  // --- TRIAC logic ---
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

  // --- Fan control ---
  analogWrite(Gate1, lowPWM);

  if (h_ave >= 50.0 && h_ave <= 60.0) {
    gate2_pwm = highPWM;
    gate3_pwm = mediumPWM;
  } else if (h_ave >= 30.0 && h_ave <= 40.0) {
    gate2_pwm = 0;
    gate3_pwm = lowPWM;
  } else {
    gate2_pwm = 0;
    gate3_pwm = 0;
  }

  analogWrite(Gate2, gate2_pwm);
  analogWrite(Gate3, gate3_pwm);

  if (gate2_pwm == highPWM && gate3_pwm == mediumPWM) {
    fanSpeedLabel = "HIGH/MEDIUM";
  } else if (gate2_pwm == 0 && gate3_pwm == lowPWM) {
    fanSpeedLabel = "OFF/LOW";
  } else if (gate2_pwm == 0 && gate3_pwm == 0) {
    fanSpeedLabel = "OFF";
  } else {
    fanSpeedLabel = "CUSTOM";
  }

  // --- TRIAC Phase Control ---
  if (doPhaseControl) {
    noInterrupts();
    doPhaseControl = false;
    interrupts();
    phaseControl();
  }

  // --- Serial Printing ---
  if (currentMillis - lastPrintTime >= printInterval) {
    lastPrintTime = currentMillis;

    Serial.print("Temperature (MAX31855): "); Serial.println(temperature);
    Serial.print("Ambient Average Temp: "); Serial.println(averageTemp);
    Serial.print("Fan3 PWM (20%): "); Serial.println(lowPWM);
    Serial.print("Fan1 PWM: "); Serial.println(pwmValue);
    Serial.print("Fan1 Speed Label: "); Serial.println(speedLabel);

    for (int i = 0; i < 8; i++) {
      Serial.print("T"); Serial.print(i + 1); Serial.print(":");
      Serial.print(Temperatures[i], 2); Serial.print(" ");
    }

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
