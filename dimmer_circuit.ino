const byte zeroCrossPin = 3;    // TLP621 output
const byte triacPin = 13;       // MOC3021 input

volatile boolean zeroCrossDetected = false;

int powerLevels[] = {0,25,50,75}; // 0 = full power, 75 = dim
int currentLevel = 0;
unsigned long lastChange = 0;

const float halfCycleMicroSec = 8333.0;  // 60Hz half-cycle = 8.33ms
const float degreesPerMicroSec = 180.0 / halfCycleMicroSec;  // for phase angle in degrees

void setup() {
  pinMode(zeroCrossPin, INPUT);
  pinMode(triacPin, OUTPUT);
  digitalWrite(triacPin, LOW);

  Serial.begin(9600);
  attachInterrupt(digitalPinToInterrupt(zeroCrossPin), zeroCrossISR, RISING);
}

void loop() {
  if (millis() - lastChange >= 2000) {
    currentLevel = (currentLevel + 1) % 4;
    lastChange = millis();

    // Get the current power level
    int percent = powerLevels[currentLevel];
    
    // Map the percentage to delay time
    int delayTime = map(percent, 0, 100, 0, 8333);

    Serial.print("percent: ");
    Serial.println(percent);
    
    // Calculate the firing angle in degrees
    float angle = delayTime * degreesPerMicroSec;

    // Calculate the power output as a percentage based on the firing angle
    float powerOut = (angle / 180.0) * 100.0;

    Serial.print("TRIAC Firing Angle: ");
    Serial.print(angle, 1);
    Serial.print("° | Power Output: ");
    Serial.print(powerOut, 0);  // Display actual power output
    Serial.println("%");
  }

  if (zeroCrossDetected) {
    zeroCrossDetected = false;

    int percent = powerLevels[currentLevel];
    int delayTime = map(percent, 0, 100, 0, 8333);

    delayMicroseconds(delayTime);
    digitalWrite(triacPin, HIGH);
    delayMicroseconds(100);
    digitalWrite(triacPin, LOW);
  }
}

void zeroCrossISR() {
  zeroCrossDetected = true;
}
