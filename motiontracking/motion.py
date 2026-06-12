#!/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3

import os
import cv2
from ultralytics import YOLO
import requests

# Serverconfig
SERVER_IP = "10.207.215.25"
SERVER_PORT = "5000"
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}/update_status"

# Camera
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

# YOLO model
model = YOLO("yolov8s-pose_ncnn_model", task="pose")

# Zone
zone_x1, zone_y1 = 0, 0
zone_x2, zone_y2 = 800, 100

# Status vlaggen
right_in_zone = False
left_in_zone = False

def send_event(state, calibration_status=None):
    payload = {"state": state}
    if calibration_status is not None:
        payload["calibration_status"] = calibration_status
    try:
        r = requests.post(SERVER_URL, json=payload, timeout=1)
        print("Verstuurd:", payload, "→", r.status_code)
        return r
    except Exception as e:
        print("Fout bij versturen:", e)
        return None

### calibratie loop ###
calibrated = False
calibration_status = "not_calibrated"
both_in_zone = False

while not calibrated:
    ret, frame = cap.read()
    if not ret:
        print("Geen frame tijdens calibratie")
        break

    results = model(frame, conf=0.25)
    keypoints = results[0].keypoints

    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]

        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y   = int(kp[9][0]),  int(kp[9][1])

        right_now_in_zone = zone_x1 < wrist_right_x < zone_x2 and zone_y1 < wrist_right_y < zone_y2
        left_now_in_zone  = zone_x1 < wrist_left_x  < zone_x2 and zone_y1 < wrist_left_y  < zone_y2
        both_now_in_zone  = right_now_in_zone and left_now_in_zone

        if both_now_in_zone and not both_in_zone:
            calibration_status = "calibrated"
        if not both_now_in_zone and both_in_zone:
            calibration_status = "not_calibrated"

        both_in_zone = both_now_in_zone

    try:
        response = requests.post(
            SERVER_URL,
            json={"state": 0, "calibration_status": calibration_status},
            timeout=1
        )
        data = response.json()
        calibrated = data.get("calibrated", False)
        print("Calibratie status van server:", calibrated)
    except Exception as e:
        print("Fout bij calibratie-request:", e)
        calibrated = False


### Main loop ###

right_in_zone = False
left_in_zone = False

while True:
    ret, frame = cap.read()
    if not ret:
        print("Geen frame meer, stoppen.")
        break

    results = model(frame, conf=0.25)
    keypoints = results[0].keypoints

    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]

        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y   = int(kp[9][0]),  int(kp[9][1])

        # Rechterpols
        right_now_in_zone = zone_x1 < wrist_right_x < zone_x2 and zone_y1 < wrist_right_y < zone_y2
        if right_now_in_zone and not right_in_zone:
            send_event(1)
        if not right_now_in_zone and right_in_zone:
            send_event(0)
        right_in_zone = right_now_in_zone

        # Linkerpols
        left_now_in_zone = zone_x1 < wrist_left_x < zone_x2 and zone_y1 < wrist_left_y < zone_y2
        if left_now_in_zone and not left_in_zone:
            send_event(1)
        if not left_now_in_zone and left_in_zone:
            send_event(0)
        left_in_zone = left_now_in_zone

cap.release()
