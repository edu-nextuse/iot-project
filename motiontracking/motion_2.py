#!/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3

import os
import cv2
from ultralytics import YOLO
import requests
import time

# Serverconfig
SERVER_IP = "fysio.mikkelserver.org"
SERVER_PORT = "5000"
SERVER_URL = f"https://{SERVER_IP}/update_status"
KP_DATA_ENDPOINT = f"https://{SERVER_IP}/keypoints"

# Camera
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

# YOLO model
model = YOLO("yolov8s-pose_ncnn_model", task="pose")

# Zone
zone_x1, zone_y1 = 600, 0
zone_x2, zone_y2 = 200, 600


def build_keypoint_dict(kp):
    return {
        "nose":           [int(kp[0][0]),  int(kp[0][1])],
        "left_eye":       [int(kp[1][0]),  int(kp[1][1])],
        "right_eye":      [int(kp[2][0]),  int(kp[2][1])],
        "left_ear":       [int(kp[3][0]),  int(kp[3][1])],
        "right_ear":      [int(kp[4][0]),  int(kp[4][1])],
        "left_shoulder":  [int(kp[5][0]),  int(kp[5][1])],
        "right_shoulder": [int(kp[6][0]),  int(kp[6][1])],
        "left_elbow":     [int(kp[7][0]),  int(kp[7][1])],
        "right_elbow":    [int(kp[8][0]),  int(kp[8][1])],
        "left_wrist":     [int(kp[9][0]),  int(kp[9][1])],
        "right_wrist":    [int(kp[10][0]), int(kp[10][1])],
        "left_hip":       [int(kp[11][0]), int(kp[11][1])],
        "right_hip":      [int(kp[12][0]), int(kp[12][1])],
        "left_knee":      [int(kp[13][0]), int(kp[13][1])],
        "right_knee":     [int(kp[14][0]), int(kp[14][1])],
        "left_ankle":     [int(kp[15][0]), int(kp[15][1])],
        "right_ankle":    [int(kp[16][0]), int(kp[16][1])]
    }


def send_keypoints(keypoints_dict):
    # YOLO geeft een array terug met 17 keypoints. Deze willen wij opslaan in een database.
    try:
        requests.post(
            KP_DATA_ENDPOINT,
            json={"timestamp": time.time(), "keypoints": keypoints_dict},
            timeout=0.5
        )
    except Exception as e:
        print(f"Watch-ERROR: send_keypoints: {e}")


def send_event(state, calibration_status=None):
    payload = {"state": state}
    if calibration_status is not None:
        payload["calibration_status"] = calibration_status
    try:
        r = requests.post(SERVER_URL, json=payload, timeout=1)
        print("Verstuurd:", payload, "→", r.status_code)
        return r
    except Exception as e:
        print(f"Watch-ERROR: send_event: {e}")


### calibratie loop ###
# Voor doekje vegen hoeft er maar 1 pols in de zone te zijn (niet allebei tegelijk zoals bij appels plukken)
calibrated = False
calibration_status = "not_calibrated"
any_in_zone = False
keypoints_dict = None

while not calibrated:
    ret, frame = cap.read()
    if not ret:
        print("Geen frame tijdens calibratie")
        break

    results = model(frame, conf=0.25)
    keypoints = results[0].keypoints

    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]
        keypoints_dict = build_keypoint_dict(kp)

        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y   = int(kp[9][0]),  int(kp[9][1])

        right_now_in_zone = zone_x1 < wrist_right_x < zone_x2 and zone_y1 < wrist_right_y < zone_y2
        left_now_in_zone  = zone_x1 < wrist_left_x  < zone_x2 and zone_y1 < wrist_left_y  < zone_y2
        any_now_in_zone   = right_now_in_zone or left_now_in_zone  # <-- 1 pols is genoeg

        if any_now_in_zone and not any_in_zone:
            calibration_status = "calibrated"
        if not any_now_in_zone and any_in_zone:
            calibration_status = "not_calibrated"

        any_in_zone = any_now_in_zone

    try:
        response = requests.post(
            SERVER_URL,
            json={"state": 0, "calibration_status": calibration_status, "keypoints": keypoints_dict},
            timeout=1
        )
        data = response.json()
        calibrated = data.get("calibrated", False)
        print("Calibratie status van server:", calibrated)
    except Exception as e:
        print(f"Watch-ERROR: calibratie-request: {e}")
        calibrated = False


### Main loop ###

wrist_in_zone = False

while True:
    ret, frame = cap.read()
    if not ret:
        print("Geen frame meer, stoppen.")
        break

    results = model(frame, conf=0.25)
    keypoints = results[0].keypoints

    kp = None
    keypoints_dict = None

    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]
        keypoints_dict = build_keypoint_dict(kp)
        send_keypoints(keypoints_dict)

        # Beide polsen checken, maar het maakt niet uit welke: 1 pols tegelijk is genoeg
        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y   = int(kp[9][0]),  int(kp[9][1])

        right_now_in_zone = zone_x1 < wrist_right_x < zone_x2 and zone_y1 < wrist_right_y < zone_y2
        left_now_in_zone  = zone_x1 < wrist_left_x  < zone_x2 and zone_y1 < wrist_left_y  < zone_y2
        now_in_zone = right_now_in_zone or left_now_in_zone

        if now_in_zone and not wrist_in_zone:
            send_event(1)
        if not now_in_zone and wrist_in_zone:
            send_event(0)
        wrist_in_zone = now_in_zone

cap.release()