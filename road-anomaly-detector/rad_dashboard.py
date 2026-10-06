# rad_dashboard_v7_simple.py
# Road Anomaly Detector — SIMPLE DIRECT THRESHOLD VERSION
# Straight threshold detection with distance offset correction
# UPDATED: gyro_z for potholes, gyro_y for bumps

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import StringIO

st.set_page_config(page_title="RAD Dashboard v7", layout="wide")

st.title("🚗 RAD Dashboard v7 — Simple Threshold Detection")
st.caption("Direct spike detection with ultrasonic offset correction")

# -------------------------------------
# Sidebar
# -------------------------------------
st.sidebar.header("Controls")
use_local = st.sidebar.checkbox("Load local sensor_log.csv", True)
uploaded = st.sidebar.file_uploader("Or upload CSV", type=["csv"])

# Detection thresholds
st.sidebar.subheader("Detection Thresholds")
pothole_gyro = st.sidebar.slider("Pothole Gyro-Z Threshold (deg/s)", 10, 60, 30)
bump_gyro = st.sidebar.slider("Bump Gyro-Y Threshold (deg/s)", 5, 40, 15)
ultrasonic_offset = st.sidebar.number_input("Ultrasonic Offset from Front Axle (cm)", 0, 30, 12)
merge_window_cm = st.sidebar.slider("Merge Events Within (cm)", 1, 10, 3)

distance_track_cm = st.sidebar.number_input("Track Length (cm)", 50, 500, 120)

if st.sidebar.button("Re-run"):
    st.rerun()

# -------------------------------------
# Load CSV
# -------------------------------------
def try_load(path="sensor_log.csv"):
    try:
        df = pd.read_csv(path)
        st.sidebar.success("Loaded local sensor_log.csv")
        return df
    except:
        return None

if uploaded:
    df = pd.read_csv(uploaded)
    st.sidebar.success("Uploaded file loaded.")
elif use_local:
    df = try_load()
else:
    df = None

if df is None:
    st.warning("Upload a CSV or enable local loading.")
    st.stop()

# -------------------------------------
# Column check & fix
# -------------------------------------
expected = ["timestamp_iso","uptime_s","distance_cm","acc_x","acc_y","acc_z","gyro_x","gyro_y","gyro_z","alert_flag"]

if len(df.columns) >= 10:
    df = df.iloc[:, :10]
    df.columns = expected
else:
    st.error("CSV missing required columns.")
    st.stop()

# Convert numerics
for col in ["distance_cm","acc_x","acc_y","acc_z","gyro_x","gyro_y","gyro_z"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df["timestamp_iso"] = pd.to_datetime(df["timestamp_iso"], errors="coerce")
df = df.sort_values("timestamp_iso").reset_index(drop=True)

# -------------------------------------
# STEP 1: Distance Preprocessing (CRITICAL)
# -------------------------------------
# st.sidebar.info("Distance preprocessing: removing outliers & smoothing")

# # Remove impossible values
# df["dist_raw"] = df["distance_cm"]
# df["dist_valid"] = df["distance_cm"].where(
#     (df["distance_cm"] > 0) & (df["distance_cm"] < 300), 
#     np.nan
# )

# # Forward-fill short gaps (sensor dropout during anomalies)
# df["dist_filled"] = df["dist_valid"].fillna(method='ffill', limit=3)

# # Aggressive median smoothing to handle ultrasonic jitter during potholes
# df["dist_smooth"] = df["dist_filled"].rolling(9, center=True, min_periods=1).median()

# # Final forward fill for any remaining NaNs
# df["distance_final"] = df["dist_smooth"].fillna(method='ffill').fillna(method='bfill')

# # -------------------------------------
# # STEP 2: Light IMU Smoothing (just remove noise)
# # -------------------------------------
# df["gyro_z_smooth"] = df["gyro_z"].rolling(3, center=True, min_periods=1).median()
# df["gyro_y_smooth"] = df["gyro_y"].rolling(3, center=True, min_periods=1).median()
# df["acc_z_smooth"] = df["acc_z"].rolling(3, center=True, min_periods=1).median()
# df["acc_x_smooth"] = df["acc_x"].rolling(3, center=True, min_periods=1).median()

# # Remove gravity from acc_z
# gravity_baseline = df["acc_z_smooth"].rolling(51, center=True, min_periods=1).mean()
# df["acc_z_nograv"] = df["acc_z_smooth"] - gravity_baseline

# -------------------------------------
# STEP 3: Direct Threshold Detection
# -------------------------------------
detections = []

# for i in range(len(df)):
#     gyro_z = df.loc[i, "gyro_z_smooth"]
#     gyro_y = df.loc[i, "gyro_y_smooth"]
#     acc_z = df.loc[i, "acc_z_nograv"]
#     acc_x = df.loc[i, "acc_x_smooth"]
#     dist = df.loc[i, "distance_final"]
for i in range(len(df)):
    gyro_z = df.loc[i,"gyro_z"]
    gyro_y = df.loc[i,"gyro_y"]
    acc_z = df.loc[i,"acc_z"]
    acc_x = df.loc[i,"acc_x"]
    dist = df.loc[i,"distance_cm"]
    
    # POTHOLE: Large gyro_z spike (positive > threshold OR negative < -threshold)
    if gyro_z > pothole_gyro or gyro_z < -pothole_gyro:
        detections.append({
            "idx": i,
            "type": "POTHOLE",
            "gyro_z": gyro_z,
            "gyro_y": gyro_y,
            "acc_z": acc_z,
            "distance_raw": dist,
            "distance_corrected": dist + ultrasonic_offset  # Add offset for front axle
        })
    
    # BUMP: gyro_y spike (positive > threshold OR negative < -threshold)
    elif gyro_y > bump_gyro or gyro_y < -bump_gyro:
        detections.append({
            "idx": i,
            "type": "BUMP",
            "gyro_z": gyro_z,
            "gyro_y": gyro_y,
            "acc_z": acc_z,
            "distance_raw": dist,
            "distance_corrected": dist + ultrasonic_offset
        })

# Convert to DataFrame
det_df = pd.DataFrame(detections)

# -------------------------------------
# STEP 4: Merge Nearby Events (same anomaly detected multiple times)
# -------------------------------------
if not det_df.empty:
    merged = []
    det_df = det_df.sort_values("distance_corrected").reset_index(drop=True)
    
    skip_until = -1
    for i, row in det_df.iterrows():
        if i < skip_until:
            continue
        
        # Find all detections within merge window
        # same_event = det_df[
        #     (det_df["distance_cm"] >= row["distance_cm"] - merge_window_cm) &
        #     (det_df["distance_cm"] <= row["distance_cm"] + merge_window_cm)] # &(det_df["type"] == row["type"])
        
        # Take the one with strongest signal
        # if row["type"] == "POTHOLE":
        #     strongest = same_event.loc[same_event["gyro_z"].abs().idxmax()]
        # else:
        #     strongest = same_event.loc[same_event["gyro_y"].abs().idxmax()]

        nearby_events = det_df[
            (det_df["distance_corrected"] >= row["distance_corrected"] - merge_window_cm) &
            (det_df["distance_corrected"] <= row["distance_corrected"] + merge_window_cm)
        ]
        
        # Calculate strength for each event (use the relevant gyro axis)
        nearby_events = nearby_events.copy()
        nearby_events["strength"] = nearby_events.apply(
            lambda r: abs(r["gyro_z"]) if r["type"] == "POTHOLE" else abs(r["gyro_y"]), 
            axis=1
        )
        
        # Take the one with strongest signal across both types
        strongest = nearby_events.loc[nearby_events["strength"].idxmax()]
        
        merged.append({
            "idx": strongest["idx"],
            "type": strongest["type"],
            "emoji": "🕳️" if strongest["type"] == "POTHOLE" else "🚧",
            "gyro_z": round(strongest["gyro_z"], 2),
            "gyro_y": round(strongest["gyro_y"], 2),
            "acc_z": round(strongest["acc_z"], 4),
            "distance_cm": round(strongest["distance_corrected"], 1)
        })
        
        skip_until = nearby_events.index.max() + 1
    
    events_df = pd.DataFrame(merged).sort_values("distance_cm").reset_index(drop=True)
else:
    events_df = pd.DataFrame()

# -------------------------------------
# Display metrics
# -------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    n_potholes = len([e for e in merged if e["type"] == "POTHOLE"]) if not events_df.empty else 0
    st.metric("🕳️ Potholes", n_potholes)
with col2:
    n_bumps = len([e for e in merged if e["type"] == "BUMP"]) if not events_df.empty else 0
    st.metric("🚧 Bumps", n_bumps)
with col3:
    st.metric("📏 Track", f"{distance_track_cm} cm")

# -------------------------------------
# Timeline plot
# -------------------------------------
st.subheader("1) Sensor Timeline — Raw Signals")

fig = go.Figure()

# Plot signals - gyro_z for potholes
fig.add_trace(go.Scatter(x=df.index, y=df["gyro_z"], 
                         name="gyro_z (raw)", mode="lines", 
                         line=dict(color="lightcoral", width=1), opacity=0.4))
fig.add_trace(go.Scatter(x=df.index, y=df["gyro_z"], 
                         name="gyro_z (smooth) - Potholes", mode="lines", 
                         line=dict(color="red", width=2)))

# Plot gyro_y for bumps
fig.add_trace(go.Scatter(x=df.index, y=df["gyro_y"], 
                         name="gyro_y (smooth) - Bumps", mode="lines", 
                         line=dict(color="cyan", width=2)))

fig.add_trace(go.Scatter(x=df.index, y=df["acc_z"]*100, 
                         name="acc_z (×100)", mode="lines",
                         line=dict(color="yellow", width=2)))

# Threshold lines
fig.add_hline(y=pothole_gyro, line_dash="dash", line_color="red", opacity=0.5, annotation_text="Pothole +")
fig.add_hline(y=-pothole_gyro, line_dash="dash", line_color="red", opacity=0.5, annotation_text="Pothole -")
fig.add_hline(y=bump_gyro, line_dash="dash", line_color="green", opacity=0.5, annotation_text="Bump +")
fig.add_hline(y=-bump_gyro, line_dash="dash", line_color="green", opacity=0.5, annotation_text="Bump -")

# Mark detections
if not events_df.empty:
    for _, r in events_df.iterrows():
        color = "red" if r["type"] == "POTHOLE" else "green"
        signal_val = r["gyro_z"] if r["type"]=="POTHOLE" else r["gyro_y"]
        fig.add_vline(x=r["idx"], line_color=color, line_width=2, opacity=0.7)
        fig.add_annotation(
            x=r["idx"], y=signal_val,
            text=f"{r['emoji']}<br>{int(r['distance_cm'])}cm",
            showarrow=True, arrowhead=2, arrowcolor=color,
            bgcolor=color, font=dict(color="white", size=10)
        )

fig.update_layout(
    template="plotly_dark", 
    height=400,
    hovermode="x unified"
)
st.plotly_chart(fig, use_container_width=True)

# -------------------------------------
# Distance preprocessing visualization
# -------------------------------------
st.subheader("2) Distance Preprocessing (Outlier Removal & Smoothing)")

fig2 = go.Figure()

# fig2.add_trace(go.Scatter(x=df.index, y=df["dist_raw"], 
#                           name="raw (with outliers)", mode="lines",
#                           line=dict(color="gray", dash="dot", width=1), opacity=0.3))
fig2.add_trace(go.Scatter(x=df.index, y=df["distance_cm"], 
                          name="distance", mode="lines",
                          line=dict(color="orange", width=2)))

# Mark detections
if not events_df.empty:
    for _, r in events_df.iterrows():
        color = "red" if r["type"] == "POTHOLE" else "green"
        fig2.add_vline(x=r["idx"], line_color=color, line_width=1, opacity=0.5)
        # Show both raw and corrected distance
        fig2.add_annotation(
            x=r["idx"], y=r["distance_cm"],
            text=f"{int(r['distance_cm'])}cm",
            showarrow=False,
            bgcolor=color, font=dict(color="white", size=9)
        )

fig2.update_layout(template="plotly_dark", height=300, yaxis_title="Distance (cm)")
st.plotly_chart(fig2, use_container_width=True)

# -------------------------------------
# Event table
# -------------------------------------
st.subheader("3) Detected Events")

if events_df.empty:
    st.warning("No events detected. Try lowering thresholds.")
else:
    st.dataframe(events_df, use_container_width=True)

# -------------------------------------
# Road path visualization
# -------------------------------------
st.subheader("4) Road Path Map")

fig3 = go.Figure()

# Draw track line
fig3.add_trace(go.Scatter(
    x=[0, distance_track_cm], y=[0, 0],
    mode="lines",
    line=dict(color="gray", width=10),
    showlegend=False,
    hoverinfo="skip"
))

# Plot events
if not events_df.empty:
    for _, r in events_df.iterrows():
        color = "red" if r["type"] == "POTHOLE" else "green"
        symbol = "x" if r["type"] == "POTHOLE" else "diamond"
        
        fig3.add_trace(go.Scatter(
            x=[r["distance_cm"]], y=[0],
            mode="markers+text",
            marker=dict(size=25, color=color, symbol=symbol, line=dict(width=2, color="white")),
            text=f"{r['emoji']}<br>{int(r['distance_cm'])}cm",
            textposition="top center",
            textfont=dict(size=12, color=color),
            showlegend=False,
            hovertemplate=f"<b>{r['type']}</b><br>Distance: {r['distance_cm']:.1f}cm<br>Gyro-Z: {r['gyro_z']}°/s<br>Gyro-Y: {r['gyro_y']}°/s<br>Acc: {r['acc_z']:.3f}g<extra></extra>"
        ))

fig3.update_layout(
    template="plotly_dark", 
    height=200,
    xaxis=dict(title="Distance (cm)", range=[-5, distance_track_cm+5]),
    yaxis=dict(visible=False, range=[-1, 1]),
    showlegend=False
)
st.plotly_chart(fig3, use_container_width=True)

# -------------------------------------
# Validation
# -------------------------------------
with st.expander("✅ Validation Check"):
    st.write("**Expected from your data:**")
    st.write("- 🕳️ Pothole at ~19 cm")
    st.write("- 🕳️ Pothole at ~41 cm")  
    st.write("- 🚧 Bump at ~62 cm")
    st.write("- 🕳️ Pothole at ~96 cm")
    st.write("")
    st.write("**Detected:**")
    if not events_df.empty:
        for _, r in events_df.iterrows():
            st.write(f"- {r['emoji']} **{r['type']}** at **{r['distance_cm']:.1f} cm** (gyro_z: {r['gyro_z']}°/s, gyro_y: {r['gyro_y']}°/s, acc_z: {r['acc_z']:.3f}g)")
    else:
        st.write("❌ Nothing detected")

# -------------------------------------
# Download
# -------------------------------------
if not events_df.empty:
    csv_buffer = StringIO()
    events_df.to_csv(csv_buffer, index=False)
    st.download_button(
        "📥 Download Events CSV", 
        csv_buffer.getvalue().encode(), 
        file_name="rad_events_simple.csv",
        mime="text/csv"
    )

st.success("✅ Simple threshold detection with distance offset correction (gyro_z for potholes, gyro_y for bumps)")