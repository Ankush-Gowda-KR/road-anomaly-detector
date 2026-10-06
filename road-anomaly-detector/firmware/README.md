# ESP32 firmware

`rad_esp32_mqtt/rad_esp32_mqtt.ino` is the v2 firmware, rewritten in October 2026 for the
MQTT port. It has **not been compiled, flashed or tested on hardware yet**. The original v1 sketch,
which POSTed readings to the Flask server, wasn't recovered.

Wiring: MPU-6050 on I2C (SDA 21, SCL 22, address 0x68); HC-SR04 trigger on GPIO 5, echo on
GPIO 18 through a voltage divider (the echo pin outputs 5 V).

Note: PubSubClient can only publish at QoS 0. For QoS 1 from the device, switch to
ESP-IDF's `esp-mqtt` or the AsyncMqttClient library.
