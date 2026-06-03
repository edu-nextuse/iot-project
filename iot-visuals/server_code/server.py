from flask import Flask, render_template, request, jsonify
import time

app = Flask(__name__)

# Globale state voor de actieve oefening en doelen
current_task = {
    "oefening_id": 0,    
    "actief": 0          
}

# Mapping van ID naar naam en doelstelling
OEFENINGEN_CONFIG = {
    1: {"naam": "Appels plukken", "doel": 15},
    2: {"naam": "Doekje vegen", "doel": 20}
}

# Globale variabelen voor de ritme- en counter-analyse
calibration_active = False
system_online = False
is_calibrated = False
motion_data = "stop"
last_state = None          
last_change_time = None    
last_received_time = None  
last_status = "unknown"    
rep_counter = 0             # Telt het aantal succesvolle herhalingen
has_hit_top = False         # Hulpvariabele om te checken of ze eerst bij '1' (boven) zijn geweest

# Ritme instellingen
MIN_FREQ = 1.0
MAX_FREQ = 5.0
TIMEOUT_LIMIT = 20.0       
CALIBRATION_DURATION = 5.0

@app.route("/")
def index():
    return render_template("portal.html")

@app.route("/buddy")
def buddy():
    return render_template("index.html")

@app.route("/control_exercise", methods=["POST"])
def control_exercise():
    global current_task, last_state, last_change_time, last_status, rep_counter, has_hit_top
    
    data = request.json
    if not data or "oefening_id" not in data or "actief" not in data:
        return jsonify({"error": "Ongeldige data"}), 400
    
    current_task["oefening_id"] = int(data["oefening_id"])
    current_task["actief"] = int(data["actief"])
    
    # Reset alle counters en variabelen bij een nieuwe start/stop
    last_state = None
    last_change_time = None
    rep_counter = 0
    has_hit_top = False
    
    if current_task["actief"] == 0:
        last_status = "unknown"
    else:
        last_status = "unknown"
        
    return jsonify({"status": "success", "current_task": current_task})

@app.route("/start_calibration", methods=["POST"])
def start_calibration():
    global calibration_active, last_change_time, is_calibrated
    calibration_active = True
    last_change_time = None
    is_calibrated = False
    return jsonify({"status": "started"})

@app.route("/calibreer")
def calibreer():
    return render_template("calibratie.html")

@app.route("/update_status", methods=["POST"])
def update_status():
    global last_state, last_change_time, last_received_time, last_status, current_task, rep_counter, has_hit_top, is_calibrated, calibration_active

    data = request.json
    if not data or "state" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    raw_state = data["state"]
    cal_status = data.get("calibration_status")  # optioneel veld

    if not is_calibrated:
        if not calibration_active:
            return jsonify({"status": "waiting", "calibrated": False})

        if cal_status == "calibrated":
            if last_change_time is None:
                last_change_time = time.time()
                print("[CALIBRATIE] Polsen in beeld, timer gestart")
            elif time.time() - last_change_time >= CALIBRATION_DURATION:
                is_calibrated = True
                calibration_active = False
                last_state = None
                last_change_time = None
                print("[SYSTEM] Calibratie voltooid!")
                return jsonify({"status": "calibrating", "calibrated": True})
            elapsed = time.time() - last_change_time
            progress = min(elapsed / CALIBRATION_DURATION * 100, 100)
            return jsonify({"status": "calibrating", "calibrated": False, "progress": progress})
        else:
            if last_change_time is not None:
                print("[CALIBRATIE] Polsen uit beeld, timer gereset")
            last_change_time = None
            return jsonify({"status": "out_of_frame", "calibrated": False, "progress": 0})

    # Gecalibreerd — normale oefening logica
    if not isinstance(raw_state, int):
        return jsonify({"status": "ignored", "reason": "Ongeldige state"}), 200

    current_state = int(raw_state)

    if current_task["actief"] == 0 or last_status == "finished":
        return jsonify({"status": "ignored", "reason": "Geen actieve of al afgeronde oefening"})

    current_time = time.time()
    last_received_time = current_time
    current_state = int(raw_state)

    if last_state is None:
        last_state = current_state
        last_change_time = current_time
        return jsonify({"status": "initialised"})

    if current_state != last_state:
        duration = current_time - last_change_time

        if duration < MIN_FREQ:
            last_status = "too_fast"
        elif duration > MAX_FREQ:
            last_status = "too_slow"
        else:
            last_status = "ok"

            if last_state == 0 and current_state == 1:
                has_hit_top = True
            elif last_state == 1 and current_state == 0 and has_hit_top:
                rep_counter += 1
                has_hit_top = False
                print(f"[COUNTER] Rep voltooid! Stand: {rep_counter}")

                oef_id = current_task["oefening_id"]
                if oef_id in OEFENINGEN_CONFIG:
                    if rep_counter >= OEFENINGEN_CONFIG[oef_id]["doel"]:
                        last_status = "finished"
                        print("[SYSTEM] Oefening succesvol afgerond!")

        print(last_state, current_state)
        last_state = current_state
        last_change_time = current_time
    else:
        time_stuck = current_time - last_change_time
        if time_stuck > MAX_FREQ and last_status != "finished":
            last_status = "no_movement"

    return jsonify({"status": "processed", "counter": rep_counter, "current_feedback": last_status})


@app.route("/current")
def current():
    global last_status, last_received_time, current_task, rep_counter
    
    if current_task["actief"] == 0:
        return jsonify({"status": "unknown", "counter": 0, "target": 0})
        
    current_time = time.time()
    
    # Timeout check (behalve als ze al klaar zijn)
    if last_status != "finished" and last_received_time and (current_time - last_received_time > TIMEOUT_LIMIT):
        last_status = "error_piconnect"
        
    oef_id = current_task["oefening_id"]
    target = OEFENINGEN_CONFIG[oef_id]["doel"] if oef_id in OEFENINGEN_CONFIG else 0
        
    return jsonify({
        "status": last_status,
        "counter": rep_counter,
        "target": target
    })
    
@app.route("/set_system", methods=["POST"])
def set_system():
    global system_online
    data = request.json
    if not data or "online" not in data:
        return jsonify({"error": "Ongeldige data"}), 400
    system_online = bool(data["online"])
    print(f"[SYSTEM] System online: {system_online}")
    return jsonify({"status": "success", "online": system_online})

@app.route("/motion_status")
def motion_status():
    global system_online
    motion = "start" if system_online else "stop"
    print(f"[MOTION] Returned: {motion} (system_online={system_online})")
    return jsonify({"motion": motion})
    
@app.route("/calibration_status")
def calibration_status():
    global is_calibrated, last_change_time
    if is_calibrated:
        return jsonify({"status": "calibrated", "progress": 100})
    if last_change_time is None:
        return jsonify({"status": "out_of_frame", "progress": 0})
    elapsed = time.time() - last_change_time
    progress = min(elapsed / CALIBRATION_DURATION * 100, 100)
    return jsonify({"status": "calibrating", "progress": progress})
    
@app.route("/reset_calibration", methods=["POST"])
def reset_calibration():
    global is_calibrated, last_change_time
    is_calibrated = False
    last_change_time = None
    return jsonify({"status": "reset"})

@app.route("/get_task", methods=["GET"])
def get_task():
    global current_task
    return jsonify(current_task)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)