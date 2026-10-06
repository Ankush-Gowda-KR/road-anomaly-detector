"""Shared MQTT settings for the RAD pipeline."""
import os

BROKER_HOST = os.getenv("RAD_BROKER_HOST", "localhost")
BROKER_PORT = int(os.getenv("RAD_BROKER_PORT", "1883"))
DEVICE_ID = os.getenv("RAD_DEVICE_ID", "rad-01")

# rad/<device>/telemetry : one JSON reading per message, QoS 1
# rad/<device>/status    : "online" (retained) / "offline" (Last Will, retained)
TELEMETRY_TOPIC = "rad/{device}/telemetry"
STATUS_TOPIC = "rad/{device}/status"
TELEMETRY_QOS = 1

CSV_FIELDS = ["timestamp_iso", "uptime_s", "distance_cm", "acc_x", "acc_y", "acc_z",
              "gyro_x", "gyro_y", "gyro_z", "alert_flag"]
