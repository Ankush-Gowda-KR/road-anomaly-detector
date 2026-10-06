# Road Anomaly Detector (RAD)

An ESP32 survey rig that finds potholes and bumps on a road and records where each one is.

Team project at PES University, Sep–Nov 2025. This is the original code as recovered in October 2026; the ESP32 sketch and the model-training script were not recovered.

## How it works

1. **The rig.** An RC car carries an ESP32, an MPU-6050-class IMU and an HC-SR04 ultrasonic sensor. It drives along a 120 cm foam test road with potholes and bumps cut into it.
2. **Sensing.** When a wheel drops into a pothole or rides over a bump, the car pitches and rolls, which shows up as a gyro spike. The HC-SR04 ranges off a fixed wall behind the start line, so its reading is the car's position along the track.
3. **Telemetry.** The ESP32 POSTs each reading (distance, 3-axis acceleration, 3-axis rotation, an on-device spike flag) as JSON over Wi-Fi to a Flask server, about 5 per second.
4. **Logging and live view.** `app.py` appends every reading to `sensor_log.csv` and pushes it to connected browsers with Socket.IO.
5. **Detection.** `rad_dashboard.py` (Streamlit) flags a pothole when |gyro_z| crosses 30 °/s and a bump when |gyro_y| crosses 15 °/s, adds a 12 cm sensor-to-front-axle offset, merges detections within 3 cm, and maps each event along the track.
6. **ML.** `rad_model_20251112_213410.joblib` is a scikit-learn Random Forest (120 trees) on four features (acceleration magnitude, rotation magnitude, gyro_z, acc_z), labelling readings Pothole, Hump, Rough or Smooth.

On the reference run (`test_log.csv`) the detector finds the track's layout: pothole, pothole, bump, pothole.

## Run it

```bash
pip install -r requirements.txt
python app.py                      # the ESP32 posts to http://<host>:5000/data
streamlit run rad_dashboard.py     # analysis dashboard on the logged CSV
```

## Known limitations

- `/data` accepts unauthenticated plain HTTP: anyone on the network can inject fake readings.
- One HTTP request per reading caps sampling at about 5 Hz.
- Development server defaults: placeholder secret key, CORS open to all origins, `debug=True`.
