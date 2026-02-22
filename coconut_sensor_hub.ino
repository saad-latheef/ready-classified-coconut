  /*
  * Coconut Quality Checker - ESP32 XIAO Sensor Hub (Weight + Height + Water)
  * Requirements: 
  * - HX711 Library by Bogdan Necula
  * - Baud: 921600 for real-time serial plotter streaming
  * 
  * Water Level Detection:
  * When weight suddenly spikes above SPIKE_THRESHOLD (coconut thrown on),
  * capture the initial weight, wait for settling, then track any increase
  * as water level (1g ≈ 1ml).
  */

  #include "HX711.h"

  // --- PIN CONFIGURATION (ESP32 XIAO) ---
  // HX711 Load Cell
  const int HX711_DOUT = 3;
  const int HX711_SCK  = 4;

  // Ultrasonic Sensor (HC-SR04)
  const int TRIG_PIN = 2;
  const int ECHO_PIN = 1;

  // --- CALIBRATION ---
  HX711 scale;
  float CALIBRATION_FACTOR = 225.358;
  long ZERO_OFFSET = 51430;

  // Ultrasonic: baseline distance (sensor to platform, no object) in cm
  float BASELINE_DISTANCE = 0.0;

  // --- WATER LEVEL DETECTION ---
  const float SPIKE_THRESHOLD = 100.0;   // grams - weight must jump above this
  const int SETTLE_COUNT = 50;           // readings to collect after spike
  const int STABLE_COUNT = 20;           // how many recent readings to average for "settled" weight

  enum WaterState {
    IDLE,         // Waiting for spike
    COLLECTING,   // Spike detected, collecting readings
    DONE          // Water level computed, waiting for removal
  };

  WaterState waterState = IDLE;
  float prevWeight = 0.0;
  float spikeReadings[200];      // Buffer for post-spike readings
  int spikeIndex = 0;
  float waterLevel = 0.0;        // Computed water level in ml
  float initialAvg = 0.0;        // Average of first few readings after spike

  float getHeight() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000); // 30ms timeout (~5m max)
    if (duration == 0) return 0.0;

    float distance = (duration * 0.0343) / 2.0; // cm
    float height = BASELINE_DISTANCE - distance + 2.0; // +2cm offset
    return (height > 0) ? height : 0.0;
  }

  void processWaterDetection(float weight) {
    switch (waterState) {
      case IDLE:
        // Check for sudden spike: weight jumps from below threshold to above
        if (weight >= SPIKE_THRESHOLD && prevWeight < SPIKE_THRESHOLD) {
          waterState = COLLECTING;
          spikeIndex = 0;
          spikeReadings[spikeIndex++] = weight;
          waterLevel = 0.0;
          Serial.println("[WATER] SPIKE DETECTED!");
        }
        break;

      case COLLECTING:
        if (weight >= SPIKE_THRESHOLD * 0.5) {  // Allow some dip during bounce
          if (spikeIndex < 200) {
            spikeReadings[spikeIndex++] = weight;
          }
          
          if (spikeIndex >= SETTLE_COUNT) {
            // Compute water level from settled readings
            float lastSum = 0;
            for (int i = spikeIndex - STABLE_COUNT; i < spikeIndex; i++) {
              lastSum += spikeReadings[i];
            }
            float settledAvg = lastSum / STABLE_COUNT;
            
            // Settled weight = water level in ml (with 10ml offset)
            waterLevel = settledAvg - 10.0;
            if (waterLevel < 0) waterLevel = 0;
            
            waterState = DONE;
            Serial.print("[WATER] SETTLED! Weight=");
            Serial.print(settledAvg, 1);
            Serial.print("g = ");
            Serial.print(waterLevel, 1);
            Serial.println("ml");
          }
        } else {
          // Weight dropped too low during collection - false trigger, reset
          waterState = IDLE;
          waterLevel = 0.0;
          spikeIndex = 0;
          Serial.println("[WATER] Reset (weight dropped during collection)");
        }
        break;

      case DONE:
        // Stay in DONE state showing the water level until weight drops (object removed)
        if (weight < SPIKE_THRESHOLD * 0.3) {
          waterState = IDLE;
          waterLevel = 0.0;
          spikeIndex = 0;
          Serial.println("[WATER] Object removed, reset");
        }
        break;
    }
    
    prevWeight = weight;
  }

  void setup() {
    Serial.begin(921600);   // VERY FAST serial for real-time streaming
    delay(500);

    // HX711
    scale.begin(HX711_DOUT, HX711_SCK);
    scale.set_offset(ZERO_OFFSET);
    scale.set_scale(CALIBRATION_FACTOR);

    // Ultrasonic
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);

    // Calibrate baseline (empty platform distance)
    delay(200);
    float sum = 0;
    for (int i = 0; i < 5; i++) {
      digitalWrite(TRIG_PIN, LOW);
      delayMicroseconds(2);
      digitalWrite(TRIG_PIN, HIGH);
      delayMicroseconds(10);
      digitalWrite(TRIG_PIN, LOW);
      long d = pulseIn(ECHO_PIN, HIGH, 30000);
      sum += (d * 0.0343) / 2.0;
      delay(50);
    }
    BASELINE_DISTANCE = sum / 5.0;
    
    Serial.println("[WATER] Water detection ready. Throw coconut to start!");
  }

  void loop() {
    if (scale.is_ready()) {
      float weight = scale.get_units(1);   // 1 sample ONLY for speed
      float height = getHeight();

      // Process water detection at native loop speed
      processWaterDetection(weight);

      // FORMAT: height,weight,water (expected by backend.py)
      Serial.print(height, 2);
      Serial.print(",");
      Serial.print(weight);
      Serial.print(",");
      Serial.println(waterLevel, 2);
    }
  }
