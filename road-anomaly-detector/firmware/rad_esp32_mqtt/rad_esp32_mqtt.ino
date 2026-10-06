// RAD v2 firmware: ESP32 + MPU-6050 + HC-SR04, publishing over MQTT.
// Rewritten Oct 2026 for the MQTT port. NOT yet flashed or tested on hardware.
// Libraries: PubSubClient (Nick O'Leary). Board: ESP32 Dev Module.

#include <WiFi.h>
#include <Wire.h>
#include <PubSubClient.h>

// ---- settings ----
const char* WIFI_SSID     = "your-ssid";
const char* WIFI_PASS     = "your-password";
const char* BROKER_HOST   = "192.168.1.10";   // laptop running Mosquitto
const uint16_t BROKER_PORT = 1883;
const char* DEVICE_ID     = "rad-01";

const uint8_t TRIG_PIN = 5;
const uint8_t ECHO_PIN = 18;                  // HC-SR04 echo is 5 V: use a divider to 3.3 V
const uint8_t MPU_ADDR = 0x68;
const uint32_t SAMPLE_MS = 200;               // ~5 Hz, same as the v1 logs

// MPU-6050 at +-4 g (8192 LSB/g) and +-500 deg/s (65.5 LSB/(deg/s))
const float ACC_LSB_PER_G  = 8192.0f;
const float GYRO_LSB_PER_DPS = 65.5f;
const float GYRO_SPIKE_DPS = 15.0f;
const float ACC_SPIKE_G    = 0.15f;

WiFiClient net;
PubSubClient mqtt(net);
char telemetryTopic[48], statusTopic[48];
float accOffset[3] = {0, 0, 0};

void mpuWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

bool mpuRead(float acc[3], float gyro[3]) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);                           // ACCEL_XOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14) != 14) return false;
  int16_t raw[7];
  for (int i = 0; i < 7; i++) raw[i] = (Wire.read() << 8) | Wire.read();
  for (int i = 0; i < 3; i++) {
    acc[i]  = raw[i] / ACC_LSB_PER_G - accOffset[i];   // raw[3] is temperature
    gyro[i] = raw[i + 4] / GYRO_LSB_PER_DPS;
  }
  return true;
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, 30000);   // 30 ms timeout (~5 m)
  return us == 0 ? -1.0f : us / 58.0f;
}

void calibrate() {                            // zero the accelerometer while the car is still
  float acc[3], gyro[3], sum[3] = {0, 0, 0};
  int n = 0;
  for (int i = 0; i < 100; i++) {
    if (mpuRead(acc, gyro)) { for (int k = 0; k < 3; k++) sum[k] += acc[k]; n++; }
    delay(5);
  }
  for (int k = 0; k < 3; k++) accOffset[k] = n ? sum[k] / n : 0;
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) delay(250);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    // Last Will: broker publishes "offline" (retained) if we drop without disconnecting
    if (mqtt.connect(DEVICE_ID, statusTopic, 1, true, "offline")) {
      mqtt.publish(statusTopic, "online", true);
    } else {
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  Wire.begin();                               // SDA 21, SCL 22
  mpuWrite(0x6B, 0x00);                       // wake up
  mpuWrite(0x1C, 0x08);                       // accel +-4 g
  mpuWrite(0x1B, 0x08);                       // gyro +-500 deg/s
  delay(100);
  calibrate();

  snprintf(telemetryTopic, sizeof telemetryTopic, "rad/%s/telemetry", DEVICE_ID);
  snprintf(statusTopic, sizeof statusTopic, "rad/%s/status", DEVICE_ID);
  connectWifi();
  mqtt.setServer(BROKER_HOST, BROKER_PORT);
  mqtt.setKeepAlive(15);
  connectMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  static uint32_t last = 0;
  if (millis() - last < SAMPLE_MS) return;
  last = millis();

  float acc[3], gyro[3];
  if (!mpuRead(acc, gyro)) return;
  float dist = readDistanceCm();

  bool gyroSpike = fabsf(gyro[1]) > GYRO_SPIKE_DPS || fabsf(gyro[2]) > GYRO_SPIKE_DPS;
  bool accSpike  = fabsf(acc[2]) > ACC_SPIKE_G;
  const char* flag = gyroSpike && accSpike ? "BOTH_SPIKE" : gyroSpike ? "GYRO_SPIKE" : accSpike ? "ACCEL_SPIKE" : "NONE";

  char payload[256];
  snprintf(payload, sizeof payload,
    "{\"timestamp\":%lu,\"distance\":%.2f,\"acc_x\":%.6f,\"acc_y\":%.6f,\"acc_z\":%.6f,"
    "\"gyro_x\":%.4f,\"gyro_y\":%.4f,\"gyro_z\":%.4f,\"alert_flag\":\"%s\"}",
    millis() / 1000, dist, acc[0], acc[1], acc[2], gyro[0], gyro[1], gyro[2], flag);
  mqtt.publish(telemetryTopic, payload);     // PubSubClient publishes at QoS 0
}
