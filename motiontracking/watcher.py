import time
import requests
import subprocess

ENDPOINT = "http://10.122.17.25:5000/motion_status"
SCRIPT = "/home/fysiofit/main.py"
python_env = "/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3"

process = None

while True:
    try:
        response = requests.get(ENDPOINT, timeout=1)
        data = response.json()
        status = data.get("motion", "stop")
    except:
        status = "stop"

    if status == "start" and process is None:
        print("Start motion tracking...")
        process = subprocess.Popen([python_env, SCRIPT])

    if status == "stop" and process is not None:
        print("Stop motion tracking...")
        process.terminate()
        process = None

    time.sleep(1)