import os
import csv
import time
from datetime import datetime
from flask import Flask, request, jsonify
from flask_socketio import SocketIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'replace_with_secure'
socketio = SocketIO(app, cors_allowed_origins="*")

CSV_FILE = "sensor_log.csv"
CSV_FIELDS = ["timestamp_iso","uptime_s","distance_cm","acc_x","acc_y","acc_z","gyro_x","gyro_y","gyro_z","alert_flag"]

# ensure CSV file exists with header
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
    print("Created CSV:", CSV_FILE)
else:
    print("Using existing CSV:", CSV_FILE)

@app.route('/')
def home():
    return "<h3>ESP32 -> Flask logging running. POST to /data (JSON)</h3>"

@app.route('/data', methods=['POST'])
def receive_data():
    if not request.is_json:
        return jsonify({"status":"error","message":"Expected JSON"}), 400
    data = request.get_json()

    # read fields (with safe defaults)
    distance = data.get("distance", None)
    upt = data.get("timestamp", None)  # uptime from ESP32 (seconds)
    ax = data.get("acc_x", None)
    ay = data.get("acc_y", None)
    az = data.get("acc_z", None)
    gx = data.get("gyro_x", None)
    gy = data.get("gyro_y", None)
    gz = data.get("gyro_z", None)
    alert = data.get("alert_flag", "NONE")

    # build row
    row = {
        "timestamp_iso": datetime.now().isoformat(),
        "uptime_s": upt,
        "distance_cm": distance,
        "acc_x": ax,
        "acc_y": ay,
        "acc_z": az,
        "gyro_x": gx,
        "gyro_y": gy,
        "gyro_z": gz,
        "alert_flag": alert
    }

    # append to CSV
    try:
        with open(CSV_FILE, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerow(row)
    except Exception as e:
        print("CSV write error:", e)
        return jsonify({"status":"error","message":"CSV write failed"}), 500

    # broadcast to any connected UI via SocketIO (optional)
    try:
        socketio.emit("new_data", row)
    except Exception:
        pass

    print("Logged:", row)
    return jsonify({"status":"ok"}), 200

if __name__ == "__main__":
    print("Server running on 0.0.0.0:5000")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
