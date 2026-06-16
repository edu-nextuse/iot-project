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

calibration_active = False
system_online = False
is_calibrated = False
last_state = None
last_change_time = None
last_received_time = None
last_status = "unknown"
rep_counter = 0
has_hit_top = False

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
    global current_task, last_state, last_change_time, last_status, rep_counter, has_hit_top

    data = request.json
    if not data or "oefening_id" not in data or "actief" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    current_task["oefening_id"] = int(data["oefening_id"])
    current_task["actief"] = int(data["actief"])
    last_state = None
    last_change_time = None
    rep_counter = 0
    has_hit_top = False
    last_status = "unknown"

    return jsonify({"status": "success", "current_task": current_task})

@app.route("/update_status", methods=["POST"])
def update_status():
    global last_state, last_change_time, last_received_time, last_status, current_task
    global rep_counter, has_hit_top, is_calibrated, calibration_active

    data = request.json
    if not data or "state" not in data:
        return jsonify({"error": "Ongeldige data"}), 400

    raw_state = data["state"]
    cal_status = data.get("calibration_status")

    if not is_calibrated:
        if not calibration_active:
            return jsonify({"status": "waiting", "calibrated": False})
        if cal_status == "calibrated":
            if last_change_time is None:
                last_change_time = time.time()
            elif time.time() - last_change_time >= CALIBRATION_DURATION:
                is_calibrated = True
                calibration_active = False
                last_state = None
                last_change_time = None
                return jsonify({"status": "calibrating", "calibrated": True})
            elapsed = time.time() - last_change_time
            progress = min(elapsed / CALIBRATION_DURATION * 100, 100)
            return jsonify({"status": "calibrating", "calibrated": False, "progress": progress})
        else:
            last_change_time = None
            return jsonify({"status": "out_of_frame", "calibrated": False, "progress": 0})

    if not isinstance(raw_state, int):
        return jsonify({"status": "ignored"}), 200

    current_state = int(raw_state)

    if current_task["actief"] == 0 or last_status == "finished":
        return jsonify({"status": "ignored"})

    current_time = time.time()
    last_received_time = current_time

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
                oef_id = current_task["oefening_id"]
                if oef_id in OEFENINGEN_CONFIG:
                    goal = OEFENINGEN_CONFIG[oef_id]["doel"]
                    if rep_counter >= goal:
                        last_status = "finished"
                        if "user_id" in session:
                            log_exercise_completion(
                                session["user_id"], oef_id,
                                OEFENINGEN_CONFIG[oef_id]["naam"],
                                rep_counter, goal, True
                            )
        last_state = current_state
        last_change_time = current_time
    else:
        time_stuck = current_time - last_change_time
        if time_stuck > MAX_FREQ and last_status != "finished":
            last_status = "no_movement"
            if "user_id" in session and current_task["actief"] == 1:
                oef_id = current_task["oefening_id"]
                if oef_id in OEFENINGEN_CONFIG:
                    log_exercise_completion(
                        session["user_id"], oef_id,
                        OEFENINGEN_CONFIG[oef_id]["naam"],
                        rep_counter, OEFENINGEN_CONFIG[oef_id]["doel"], False
                    )

    return jsonify({"status": "processed", "counter": rep_counter, "current_feedback": last_status})

@app.route("/current")
def current():
    global last_status, last_received_time, current_task, rep_counter
    if current_task["actief"] == 0:
        return jsonify({"status": "unknown", "counter": 0, "target": 0})
    current_time = time.time()
    if last_status != "finished" and last_received_time and (current_time - last_received_time > TIMEOUT_LIMIT):
        last_status = "error_piconnect"
    oef_id = current_task["oefening_id"]
    target = OEFENINGEN_CONFIG[oef_id]["doel"] if oef_id in OEFENINGEN_CONFIG else 0
    return jsonify({"status": last_status, "counter": rep_counter, "target": target})

@app.route("/set_system", methods=["POST"])
def set_system():
    global system_online
    data = request.json
    if not data or "online" not in data:
        return jsonify({"error": "Ongeldige data"}), 400
    system_online = bool(data["online"])
    return jsonify({"status": "success", "online": system_online})

@app.route("/motion_status")
def motion_status():
    motion = "start" if system_online else "stop"
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

@app.route("/start_calibration", methods=["POST"])
def start_calibration():
    global calibration_active, last_change_time, is_calibrated
    calibration_active = True
    last_change_time = None
    is_calibrated = False
    return jsonify({"status": "started"})

@app.route("/reset_calibration", methods=["POST"])
def reset_calibration():
    global is_calibrated, last_change_time
    is_calibrated = False
    last_change_time = None
    return jsonify({"status": "reset"})

@app.route("/get_task")
def get_task():
    return jsonify(current_task)

@app.route("/api/streak")
@login_required
def api_streak():
    user_id = session["user_id"]
    return jsonify(get_streak_data(user_id))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)