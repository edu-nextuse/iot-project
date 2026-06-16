from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
import sqlite3
import hashlib
import time
import os
from datetime import date, datetime, timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)

DB_PATH = "fysiofit.db"

# database initialisatie en verbinding

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS exercise_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            reps_done INTEGER NOT NULL,
            reps_goal INTEGER NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            logged_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# authorisatie

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    conn.close()
    return user

# reeks

def get_streak_data(user_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT DISTINCT DATE(logged_at) as day
        FROM exercise_log
        WHERE user_id = ? AND completed = 1
        ORDER BY day DESC
    """, (user_id,)).fetchall()
    conn.close()

    days_with_exercise = [row["day"] for row in rows]

    today = date.today()
    streak = 0
    check_day = today

    for day_str in days_with_exercise:
        day = date.fromisoformat(day_str)
        if day == check_day:
            streak += 1
            check_day -= timedelta(days=1)
        elif day < check_day:
            break

    week = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        week.append({
            "date": d.isoformat(),
            "label": ["Ma", "Di", "Wo", "Do", "Vr", "Za", "Zo"][d.weekday()],
            "done": d.isoformat() in days_with_exercise,
            "today": d == today
        })

    return {
        "streak": streak,
        "week": week,
        "total_days": len(days_with_exercise)
    }

def log_exercise_completion(user_id, exercise_id, exercise_name, reps_done, reps_goal, completed):
    conn = get_db()
    today = date.today().isoformat()

    existing = conn.execute("""
        SELECT id FROM exercise_log
        WHERE user_id = ? AND exercise_id = ? AND DATE(logged_at) = ?
    """, (user_id, exercise_id, today)).fetchone()

    if existing:
        conn.execute("""
            UPDATE exercise_log SET reps_done = ?, completed = ?, logged_at = ? WHERE id = ?
        """, (reps_done, int(completed), datetime.now().isoformat(), existing["id"]))
    else:
        conn.execute("""
            INSERT INTO exercise_log (user_id, exercise_id, exercise_name, reps_done, reps_goal, completed, logged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, exercise_id, exercise_name, reps_done, reps_goal, int(completed), datetime.now().isoformat()))

    conn.commit()
    conn.close()

# oefening status en configuratie

current_task = {"oefening_id": 0, "actief": 0}

OEFENINGEN_CONFIG = {
    1: {"naam": "Appels plukken", "doel": 15},
    2: {"naam": "Doekje vegen", "doel": 20}
}

# Ritme instellingen (Blijven globaal)
MIN_FREQ = 1.0
MAX_FREQ = 5.0
TIMEOUT_LIMIT = 20.0
CALIBRATION_DURATION = 5.0

# app routes

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("portal"))
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user and user["password_hash"] == hash_password(password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("portal"))
        error = "Onjuist e-mailadres of wachtwoord."
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("portal"))
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or not password:
            error = "Vul alle velden in."
        elif len(password) < 6:
            error = "Wachtwoord moet minimaal 6 tekens zijn."
        else:
            try:
                conn = get_db()
                conn.execute("""
                    INSERT INTO users (name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                """, (name, email, hash_password(password), datetime.now().isoformat()))
                conn.commit()
                user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
                conn.close()
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]
                return redirect(url_for("portal"))
            except sqlite3.IntegrityError:
                error = "Dit e-mailadres is al in gebruik."
    return render_template("register.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# main portal en profiel routes
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
@login_required
def portal():
    user = get_current_user()
    streak_data = get_streak_data(user["id"])
    return render_template("portal.html", user=user, streak=streak_data)

@app.route("/profiel")
@login_required
def profiel():
    user = get_current_user()
    streak_data = get_streak_data(user["id"])
    conn = get_db()
    recent_logs = conn.execute("""
        SELECT * FROM exercise_log WHERE user_id = ? ORDER BY logged_at DESC LIMIT 20
    """, (user["id"],)).fetchall()
    conn.close()
    return render_template("profiel.html", user=user, streak=streak_data, logs=recent_logs)


@app.route("/buddy")
@login_required
def buddy():
    user = get_current_user()
    return render_template("index.html", user=user)

@app.route("/calibreer")
@login_required
def calibreer():
    return render_template("calibratie.html")

# oefening routes


@app.route("/control_exercise", methods=["POST"])
@login_required
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



@app.route("/update_status", methods=["POST"])
def update_status():
    s = get_session()

    data = request.json
    if not data or "state" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    raw_state = data["state"]
    cal_status = data.get("calibration_status")

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

    if not isinstance(raw_state, int):
        return jsonify({"status": "ignored"}), 200

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
                        if "user_id" in session:
                            log_exercise_completion(
                                session["user_id"], oef_id,
                                OEFENINGEN_CONFIG[oef_id]["naam"],
                                s["rep_counter"], OEFENINGEN_CONFIG[oef_id]["doel"], True
                            )

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


@app.route("/api/streak")
@login_required
def api_streak():
    user_id = session["user_id"]
    return jsonify(get_streak_data(user_id))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)