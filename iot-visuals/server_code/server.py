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
last_state = None          
last_change_time = None    
last_received_time = None  
last_status = "unknown"    
rep_counter = 0             # Telt het aantal succesvolle herhalingen
has_hit_top = False         # Hulpvariabele om te checken of ze eerst bij '1' (boven) zijn geweest

# Ritme instellingen
MIN_FREQ = 2.0
MAX_FREQ = 5.0
TIMEOUT_LIMIT = 10.0       

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

@app.route("/update_status", methods=["POST"])
def update_status():
    global last_state, last_change_time, last_received_time, last_status, current_task, rep_counter, has_hit_top
    
    if current_task["actief"] == 0 or last_status == "finished":
        return jsonify({"status": "ignored", "reason": "Geen actieve of al afgeronde oefening"})

    data = request.json
    if not data or "state" not in data:
        return jsonify({"error": "Ongeldige data"}), 400
    
    current_time = time.time()
    last_received_time = current_time 
    current_state = int(data["state"])

    # Initialisatie bij de allereerste call
    if last_state is None:
        last_state = current_state
        last_change_time = current_time
        return jsonify({"status": "initialised"})

    # Check op verandering van positie
    if current_state != last_state:
        duration = current_time - last_change_time
        
        # Validatie: was het tempo goed?
        if duration < MIN_FREQ:
            last_status = "too_fast"
        elif duration > MAX_FREQ:
            last_status = "too_slow"
        else:
            last_status = "ok"
            
            # --- COUNTER LOGICA (0 -> 1 -> 0) ---
            if last_state == 0 and current_state == 1:
                # Handen gaan omhoog in goed tempo
                has_hit_top = True
            elif last_state == 1 and current_state == 0 and has_hit_top:
                # Handen gaan weer omlaag én ze zijn netjes boven geweest
                rep_counter += 1
                has_hit_top = False # Reset voor de volgende herhaling
                print(f"[COUNTER] Rep voltooid! Stand: {rep_counter}")
                
                # Check of het doel van de huidige oefening is bereikt
                oef_id = current_task["oefening_id"]
                if oef_id in OEFENINGEN_CONFIG:
                    if rep_counter >= OEFENINGEN_CONFIG[oef_id]["doel"]:
                        last_status = "finished"
                        print("[SYSTEM] Oefening succesvol afgerond!")
            
        last_state = current_state
        last_change_time = current_time
    else:
        # Check op inactiviteit
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

@app.route("/get_task", methods=["GET"])
def get_task():
    global current_task
    return jsonify(current_task)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)