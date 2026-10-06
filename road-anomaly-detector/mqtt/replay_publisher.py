"""Replay a recorded run over MQTT, exactly as the ESP32 would publish it.

Lets you demo and test the pipeline with no hardware.
Usage: python mqtt/replay_publisher.py test_log.csv [--speed 1.0]
"""
import argparse
import csv
import json
import time
from datetime import datetime

import paho.mqtt.client as mqtt

from config import BROKER_HOST, BROKER_PORT, DEVICE_ID, STATUS_TOPIC, TELEMETRY_QOS, TELEMETRY_TOPIC


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--speed", type=float, default=1.0, help="2.0 = twice real time")
    args = ap.parse_args()

    status = STATUS_TOPIC.format(device=DEVICE_ID)
    telemetry = TELEMETRY_TOPIC.format(device=DEVICE_ID)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=DEVICE_ID)
    # Broker announces the device offline if it drops without a clean disconnect
    client.will_set(status, "offline", qos=1, retain=True)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=15)
    client.loop_start()
    client.publish(status, "online", qos=1, retain=True)

    with open(args.csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    prev = None
    for r in rows:
        t = datetime.fromisoformat(r["timestamp_iso"])
        if prev is not None:
            time.sleep(max(0.0, (t - prev).total_seconds()) / args.speed)
        prev = t
        payload = {
            "timestamp": num(r["uptime_s"]),
            "distance": num(r["distance_cm"]),
            "acc_x": num(r["acc_x"]), "acc_y": num(r["acc_y"]), "acc_z": num(r["acc_z"]),
            "gyro_x": num(r["gyro_x"]), "gyro_y": num(r["gyro_y"]), "gyro_z": num(r["gyro_z"]),
            "alert_flag": r["alert_flag"],
        }
        client.publish(telemetry, json.dumps(payload), qos=TELEMETRY_QOS).wait_for_publish()

    client.publish(status, "offline", qos=1, retain=True).wait_for_publish()
    client.loop_stop()
    client.disconnect()
    print(f"Replayed {len(rows)} readings to {telemetry}")


if __name__ == "__main__":
    main()
