import time
import requests
import subprocess

#script naar de while loop verplaatst
SERVER_IP = "fysio.mikkelserver.org"
SERVER_PORT = "5000"
ENDPOINT = f"https://{SERVER_IP}/motion_status"
ERROR_ENDPOINT = f"https://{SERVER_IP}/error"
python_env = "/home/fysiofit/miniforge3/envs/ultralytics-env/bin/python3"

process = None


def send_error(error):
    payload = {"error": str(error)}
    try:
        requests.post(ERROR_ENDPOINT, json=payload, timeout=1)
    except Exception as e:
        print(f"Watch-ERROR: send_error: {e}")

while True:
    try:
        data = requests.get(ENDPOINT, timeout=1).json()
        status = data.get("motion")

        exercise_id = data.get("exercise", 1) 
        if not data or not status or not exercise_name:
            raise ValueError(f"Ongeldige server response! (Geen leuke error)")


    except Exception as e:
        status = "stop"
        send_error(e)

    #START
    if status == "start" and process is None:
        print("Start motion tracking...")

        process = subprocess.Popen(
            [python_env, SCRIPT],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

    # ERROR handeling *Kim glundert*
    if process is not None:
        line = process.stdout.readline()

        if line:
            line = line.strip()

            if "Watch-ERROR: " in line:
                send_error(line)

        if process.poll() is not None:
            print("Process gestopt")
            process = None

    # STOP
    if status == "stop" and process is not None:
        print("Stop motion tracking...")
        process.terminate()
        process = None

    time.sleep(0.01)
