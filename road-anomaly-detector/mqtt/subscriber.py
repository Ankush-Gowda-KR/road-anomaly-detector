"""Subscribe to every RAD device's telemetry and append it to a CSV.

Writes the same columns as the v1 Flask server, so rad_dashboard.py reads the output unchanged.
Usage: python mqtt/subscriber.py [--csv sensor_log.csv]
"""
import argparse
import csv
import json
import os
from datetime import datetime

import paho.mqtt.client as mqtt

from config import BROKER_HOST, BROKER_PORT, CSV_FIELDS, STATUS_TOPIC, TELEMETRY_QOS, TELEMETRY_TOPIC


def ensure_header(path):
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="sensor_log.csv")
    args = ap.parse_args()
    ensure_header(args.csv)

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"Connected to {BROKER_HOST}:{BROKER_PORT} ({reason_code})")
        client.subscribe(TELEMETRY_TOPIC.format(device="+"), qos=TELEMETRY_QOS)
        client.subscribe(STATUS_TOPIC.format(device="+"), qos=1)

    def on_message(client, userdata, msg):
        device = msg.topic.split("/")[1]
        if msg.topic.endswith("/status"):
            print(f"[{device}] status: {msg.payload.decode()}")
            return
        try:
            d = json.loads(msg.payload)
        except json.JSONDecodeError:
            print(f"[{device}] dropped malformed payload")
            return
        row = {
            "timestamp_iso": datetime.now().isoformat(),
            "uptime_s": d.get("timestamp"),
            "distance_cm": d.get("distance"),
            "acc_x": d.get("acc_x"), "acc_y": d.get("acc_y"), "acc_z": d.get("acc_z"),
            "gyro_x": d.get("gyro_x"), "gyro_y": d.get("gyro_y"), "gyro_z": d.get("gyro_z"),
            "alert_flag": d.get("alert_flag", "NONE"),
        }
        with open(args.csv, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writerow(row)
        if row["alert_flag"] != "NONE":
            print(f"[{device}] {row['alert_flag']} at {row['distance_cm']} cm")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="rad-logger")
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_forever()


if __name__ == "__main__":
    main()
