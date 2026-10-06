"""Compare the v1 Random Forest with the v1 gyro thresholds on a recorded run.

Usage: python analysis/compare_model_vs_thresholds.py test_log.csv [--plot docs/test_run.png]
"""
import argparse

import joblib
import numpy as np
import pandas as pd

POTHOLE_GYRO_Z = 30.0   # deg/s, rad_dashboard.py defaults
BUMP_GYRO_Y = 15.0
OFFSET_CM = 12.0        # ultrasonic sensor to front axle
MODEL = "rad_model_20251112_213410.joblib"


def load(path):
    d = pd.read_csv(path)
    for c in ["distance_cm", "acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.fillna(0)


def threshold_label(r):
    if abs(r.gyro_z) > POTHOLE_GYRO_Z:
        return "Pothole"
    if abs(r.gyro_y) > BUMP_GYRO_Y:
        return "Bump"
    return "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--plot")
    args = ap.parse_args()

    d = load(args.csv)
    model = joblib.load(MODEL)
    feats = pd.DataFrame({
        "accel_mag": np.sqrt(d.acc_x**2 + d.acc_y**2 + d.acc_z**2),
        "gyro_mag": np.sqrt(d.gyro_x**2 + d.gyro_y**2 + d.gyro_z**2),
        "gyro_z": d.gyro_z,
        "acc_z": d.acc_z,
    })
    d["model"] = model.predict(feats)
    d["threshold"] = d.apply(threshold_label, axis=1)

    print("Feature importances:", dict(zip(model.feature_names_in_, model.feature_importances_.round(3))))
    print("Model labels:", d.model.value_counts().to_dict())
    print("\nReadings either method flags:")
    flagged = d[(d.model != "Smooth") | (d.threshold != "-")]
    print(flagged[["distance_cm", "gyro_y", "gyro_z", "model", "threshold"]].to_string())

    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        d = d.sort_values("distance_cm")
        x = d.distance_cm + OFFSET_CM
        fig, ax = plt.subplots(figsize=(9, 3.6))
        ax.plot(x, d.gyro_z, label="gyro_z (potholes)", color="#c0392b")
        ax.plot(x, d.gyro_y, label="gyro_y (bumps)", color="#2471a3")
        for y, c in [(POTHOLE_GYRO_Z, "#c0392b"), (-POTHOLE_GYRO_Z, "#c0392b"), (BUMP_GYRO_Y, "#2471a3"), (-BUMP_GYRO_Y, "#2471a3")]:
            ax.axhline(y, color=c, ls="--", lw=0.8, alpha=0.6)
        ax.set_xlabel("Position along track (cm)")
        ax.set_ylabel("Rotation rate (°/s)")
        ax.set_title("Reference run: pothole, pothole, bump, pothole")
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        fig.savefig(args.plot, dpi=150)
        print("Saved", args.plot)


if __name__ == "__main__":
    main()
