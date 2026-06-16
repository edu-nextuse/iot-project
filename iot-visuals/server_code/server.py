from flask import Flask, render_template, request, jsonify, session
import time

app = Flask(__name__)
app.secret_key = "jouw_geheime_sleutel_hier"

# Mapping van ID naar naam en doelstelling (Blijft globaal want dit verandert niet)
OEFENINGEN_CONFIG = {
    1: {"naam": "Appels plukken", "doel": 15},
    2: {"naam": "Doekje vegen", "doel": 20}
}

# Ritme instellingen (Blijven globaal)
MIN_FREQ = 1.0
MAX_FREQ = 5.0
TIMEOUT_LIMIT = 20.0
CALIBRATION_DURATION = 5.0

# State per IP opslaan
sessions = {}

def get_session():
    ip = request.remote_addr
    if ip not in sessions:
        sessions[ip] = {
            "current_task": {"oefening_id": 0, "actief": 0},
            "calibration_active": False,
            "system_online": False,
            "is_calibrated": False,
            "motion_data": "stop",
            "last_state": None,
            "last_change_time": None,
            "last_received_time": None,
            "last_status": "unknown",
            "rep_counter": 0,
            "has_hit_top": False,
        }
    return sessions[ip]


@app.route("/")
def index():
    return render_template("portal.html")


@app.route("/buddy")
def buddy():
    return render_template("index.html")


@app.route("/control_exercise", methods=["POST"])
def control_exercise():
    s = get_session()

    data = request.json
    if not data or "oefening_id" not in data or "actief" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    s["current_task"]["oefening_id"] = int(data["oefening_id"])
    s["current_task"]["actief"] = int(data["actief"])

    # Reset alle counters en variabelen bij een nieuwe start/stop
    s["last_state"] = None
    s["last_change_time"] = None
    s["rep_counter"] = 0
    s["has_hit_top"] = False

    if s["current_task"]["actief"] == 0:
        s["last_status"] = "unknown"
    else:
        s["last_status"] = "unknown"

    return jsonify({"status": "success", "current_task": s["current_task"]})


@app.route("/start_calibration", methods=["POST"])
def start_calibration():
    s = get_session()
    s["calibration_active"] = True
    s["last_change_time"] = None
    s["is_calibrated"] = False
    return jsonify({"status": "started"})


@app.route("/calibreer")
def calibreer():
    return render_template("calibratie.html")


@app.route("/update_status", methods=["POST"])
def update_status():
    s = get_session()

    data = request.json
    if not data or "state" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    raw_state = data["state"]
    cal_status = data.get("calibration_status")  # optioneel veld

    if not s["is_calibrated"]:
        if not s["calibration_active"]:
            return jsonify({"status": "waiting", "calibrated": False})

        if cal_status == "calibrated":
            if s["last_change_time"] is None:
                s["last_change_time"] = time.time()
                print("[CALIBRATIE] Polsen in beeld, timer gestart")
            elif time.time() - s["last_change_time"] >= CALIBRATION_DURATION:
                s["is_calibrated"] = True
                s["calibration_active"] = False
                s["last_state"] = None
                s["last_change_time"] = None
                print("[SYSTEM] Calibratie voltooid!")
                return jsonify({"status": "calibrating", "calibrated": True})

            elapsed = time.time() - s["last_change_time"]
            progress = min(elapsed / CALIBRATION_DURATION * 100, 100)
            return jsonify({"status": "calibrating", "calibrated": False, "progress": progress})
        else:
            if s["last_change_time"] is not None:
                print("[CALIBRATIE] Polsen uit beeld, timer gereset")
            s["last_change_time"] = None
            return jsonify({"status": "out_of_frame", "calibrated": False, "progress": 0})

    # Gecalibreerd — normale oefening logica
    if not isinstance(raw_state, int):
        return jsonify({"status": "ignored", "reason": "Ongeldige state"}), 200

    current_state = int(raw_state)

    if s["current_task"]["actief"] == 0 or s["last_status"] == "finished":
        return jsonify({"status": "ignored", "reason": "Geen actieve of al afgeronde oefening"})

    current_time = time.time()
    s["last_received_time"] = current_time

    if s["last_state"] is None:
        s["last_state"] = current_state
        s["last_change_time"] = current_time
        return jsonify({"status": "initialised"})

    if current_state != s["last_state"]:
        duration = current_time - s["last_change_time"]

        if duration < MIN_FREQ:
            s["last_status"] = "too_fast"
        elif duration > MAX_FREQ:
            s["last_status"] = "too_slow"
        else:
            s["last_status"] = "ok"

            if s["last_state"] == 0 and current_state == 1:
                s["has_hit_top"] = True
            elif s["last_state"] == 1 and current_state == 0 and s["has_hit_top"]:
                s["rep_counter"] += 1
                s["has_hit_top"] = False
                print(f"[COUNTER] Rep voltooid! Stand: {s['rep_counter']}")

                oef_id = s["current_task"]["oefening_id"]
                if oef_id in OEFENINGEN_CONFIG:
                    if s["rep_counter"] >= OEFENINGEN_CONFIG[oef_id]["doel"]:
                        s["last_status"] = "finished"
                        print("[SYSTEM] Oefening succesvol afgerond!")

        print(s["last_state"], current_state)
        s["last_state"] = current_state
        s["last_change_time"] = current_time
    else:
        time_stuck = current_time - s["last_change_time"]
        if time_stuck > MAX_FREQ and s["last_status"] != "finished":
            s["last_status"] = "no_movement"

    return jsonify({"status": "processed", "counter": s["rep_counter"], "current_feedback": s["last_status"]})


@app.route("/current")
def current():
    s = get_session()

    if s["current_task"]["actief"] == 0:
        return jsonify({"status": "unknown", "counter": 0, "target": 0})

    current_time = time.time()

    # Timeout check (behalve als ze al klaar zijn)
    if s["last_status"] != "finished" and s["last_received_time"] and (current_time - s["last_received_time"] > TIMEOUT_LIMIT):
        s["last_status"] = "error_piconnect"

    oef_id = s["current_task"]["oefening_id"]
    target = OEFENINGEN_CONFIG[oef_id]["doel"] if oef_id in OEFENINGEN_CONFIG else 0

    return jsonify({
        "status": s["last_status"],
        "counter": s["rep_counter"],
        "target": target
    })


@app.route("/set_system", methods=["POST"])
def set_system():
    s = get_session()
    data = request.json
    if not data or "online" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    s["system_online"] = bool(data["online"])
    print(f"[SYSTEM] System online: {s['system_online']}")
    return jsonify({"status": "success", "online": s["system_online"]})


@app.route("/motion_status")
def motion_status():
    s = get_session()
    motion = "start" if s["system_online"] else "stop"
    print(f"[MOTION] Returned: {motion} (system_online={s['system_online']})")
    return jsonify({"motion": motion})


@app.route("/calibration_status")
def calibration_status():
    s = get_session()
    if s["is_calibrated"]:
        return jsonify({"status": "calibrated", "progress": 100})
    if s["last_change_time"] is None:
        return jsonify({"status": "out_of_frame", "progress": 0})

    elapsed = time.time() - s["last_change_time"]
    progress = min(elapsed / CALIBRATION_DURATION * 100, 100)
    return jsonify({"status": "calibrating", "progress": progress})


@app.route("/reset_calibration", methods=["POST"])
def reset_calibration():
    s = get_session()
    s["is_calibrated"] = False
    s["last_change_time"] = None
    return jsonify({"status": "reset"})


@app.route("/get_task", methods=["GET"])
def get_task():
    s = get_session()
    return jsonify(s["current_task"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)