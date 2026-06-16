import time
import requests
import subprocess
from dotenv import load_dotenv
import os

env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

#script naar de while loop verplaatst
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = os.getenv('SERVER_PORT')
ENDPOINT = f"{SERVER_IP}:{SERVER_PORT}/motion_status"
ERROR_ENDPOINT = f"{SERVER_IP}:{SERVER_PORT}/error"
python_env = os.getenv('python_env')

process = None
print(SERVER_IP, python_env)

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
        print(data)
        exercise_id = data.get("exercise", 1) 
        if not data or not status or not exercise_id:
            raise ValueError(f"Ongeldige server response! (Geen leuke error)")

        SCRIPT = f"/home/fysiofit/buddy_code/motions/motion_{exercise_id}.py"

    except Exception as e:
        status = "stop"
        send_error(e)

    #START
    if status == "start" and process is None:
        print("Start motion tracking...")

        process = subprocess.Popen(
            [python_env, SCRIPT, "-u"],
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
                print(line)
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
