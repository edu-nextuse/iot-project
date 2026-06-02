import cv2
from ultralytics import YOLO
import requests

# Server configuratie
SERVER_IP = "10.122.17.25"
SERVER_PORT = "5000"
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}/update_status"

# Camera setup (geen venster)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

# YOLO model
model = YOLO("yolov8s-pose_ncnn_model", task="pose")

# Zone
zone_x1, zone_y1 = 0, 0
zone_x2, zone_y2 = 800, 100

# Status flags
right_in_zone = False
left_in_zone = False

def send_event(status):
    payload = {"state": status}
    try:
        requests.post(SERVER_URL, json=payload, timeout=1)
        print("Verstuurd:", payload)
    except Exception as e:
        print("Fout bij versturen:", e)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO inference
    results = model(frame, conf=0.25)

    # Keypoints ophalen
    keypoints = results[0].keypoints
    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]

        # Polsposities
        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y = int(kp[9][0]), int(kp[9][1])

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

# Cleanup
cap.release()