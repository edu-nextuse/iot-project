#!/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3

import cv2
from ultralytics import YOLO
import requests

#Variabel gebabbel
SERVER_IP = "10.207.215.25"
SERVER_PORT = "5000"

SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}/update_status"


cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)

model = YOLO("yolov8s-pose_ncnn_model", task="pose")

# Definieer de oefening zone:
zone_x1, zone_y1 = 0, 0
zone_x2, zone_y2 = 800, 100

cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Camera", 1280, 960)

#status vlaggen
right_in_zone = False
left_in_zone = False

def send_event(status):
    payload = {
        "state": status,
    }
    try:
        requests.post(SERVER_URL, json=payload, timeout=1)
        print("Verstuurd:", payload)
    except Exception as e:
        print("Fout bij versturen:", e)

calibration_status = "not_calibrated"
calibrated = False

while not calibrated:
    
    ret, frame = cap.read()
    if not ret:
        break    
    
    # YOLO inference
    results = model(frame, conf=0.25)
    annotated = results[0].plot()

    # Teken de zone
    cv2.rectangle(annotated, (zone_x1, zone_y1), (zone_x2, zone_y2), (0,255,0), 2)

    # Keypoints ophalen
    keypoints = results[0].keypoints
    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]

        # Polsposities
        wrist_right_x, wrist_right_y = int(kp[10][0]), int(kp[10][1])
        wrist_left_x, wrist_left_y = int(kp[9][0]), int(kp[9][1])
    
        right_now_in_zone = zone_x1 < wrist_right_x < zone_x2 and zone_y1 < wrist_right_y < zone_y2
        left_now_in_zone = zone_x1 < wrist_left_x < zone_x2 and zone_y1 < wrist_left_y < zone_y2
        both_now_in_zone = right_now_in_zone and left_now_in_zone
        both_in_zone = False
    
        #Calibratie
        if both_now_in_zone and not both_in_zone:
            calibration_status = "calibrated"
        if not both_now_in_zone and both_in_zone:
            calibration_status = "not_calibrated"
        both_in_zone = both_now_in_zone
        
    try:
        response = requests.post(SERVER_URL, json={"state":0,"calibration_status":calibration_status}, timeout=1)
        data = response.json()
        calibrated = data.get("calibrated", False)
    except:
        calibrated = False
        
    cv2.imshow("Camera", annotated)

    if cv2.waitKey(1) == ord("q"):
        break


while True:
    ret, frame = cap.read()
    if not ret:
        break
    # YOLO inference
    results = model(frame, conf=0.25)
    annotated = results[0].plot()

    # Teken de zone
    cv2.rectangle(annotated, (zone_x1, zone_y1), (zone_x2, zone_y2), (0,255,0), 2)
    
    if keypoints is not None and len(keypoints) > 0:
        kp = keypoints[0].xy[0]

        # Teken rechter pols
        cv2.circle(annotated, (wrist_right_x, wrist_right_y), 8, (0,0,255), -1)
        
        # Teken linker pols
        cv2.circle(annotated, (wrist_left_x, wrist_left_y), 8, (0,0,255), -1)

        # Check of de rechter pols in zone is
        if right_now_in_zone and not right_in_zone:
            send_event(1) # pols in de zone
        if not right_now_in_zone and right_in_zone:
            send_event(0) # pols uit de zone 
        right_in_zone = right_now_in_zone
        
        # Linkerpols                
        if left_now_in_zone and not left_in_zone:
            send_event(1) # pols in de zone
        if not left_now_in_zone and left_in_zone:
            send_event(0) # pols uit de zone
        left_in_zone = left_now_in_zone

    cv2.imshow("Camera", annotated)

    if cv2.waitKey(1) == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
