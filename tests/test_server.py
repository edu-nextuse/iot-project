import pytest
import time
import sys
import os

# Zorg dat server.py importeerbaar is
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from server import app, init_db, sessions

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Flask test client met een schone database en sessie."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"

    with app.test_client() as client:
        with app.app_context():
            init_db()
        # Schone sessie voor elke test
        sessions.clear()
        yield client
        sessions.clear()

def start_oefening(client, oefening_id=1):
    """Hulpfunctie: log in en start een oefening."""
    # Registreer + login testgebruiker
    client.post("/register", data={
        "name": "Test",
        "email": "test@test.nl",
        "password": "test123"
    })
    client.post("/login", data={
        "email": "test@test.nl",
        "password": "test123"
    })
    # Zet systeem online en start calibratie
    client.post("/set_system", json={"online": True})
    client.post("/start_calibration")
    # Simuleer calibratie voltooid
    s = list(sessions.values())[0]
    s["is_calibrated"] = True
    s["calibration_active"] = False
    # Start oefening
    client.post("/control_exercise", json={"oefening_id": oefening_id, "actief": 1})

def update(client, state):
    """Stuur een state update naar de server."""
    return client.post("/update_status", json={
        "state": state,
        "calibration_status": "not_calibrated"
    })

def current(client):
    """Haal huidige status op."""
    return client.get("/current")

# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFysioFitLogic:

    def test_perfect_rep_tempo(self, client):
        """Een herhaling binnen 1-5 seconden geeft status 'ok' en telt mee."""
        start_oefening(client)
        s = list(sessions.values())[0]

        # Startpositie
        update(client, 0)

        # Simuleer 3 seconden wachten door last_change_time terug te zetten
        s["last_change_time"] -= 3.0

        res = update(client, 1)
        assert res.json["current_feedback"] == "ok"

        s["last_change_time"] -= 3.0
        res = update(client, 0)

        assert res.json["counter"] == 1
        assert res.json["current_feedback"] == "ok"

    def test_rep_too_fast(self, client):
        """Beweging binnen 0.5 seconden geeft 'too_fast'."""
        start_oefening(client)
        s = list(sessions.values())[0]

        update(client, 0)
        s["last_change_time"] -= 0.5  # slechts 0.5 seconden verstreken

        res = update(client, 1)
        assert res.json["current_feedback"] == "too_fast"

    def test_rep_too_slow(self, client):
        """Beweging na meer dan 5 seconden geeft 'too_slow'."""
        start_oefening(client)
        s = list(sessions.values())[0]

        update(client, 0)
        s["last_change_time"] -= 5.5  # 5.5 seconden verstreken

        res = update(client, 1)
        assert res.json["current_feedback"] == "too_slow"

    def test_patient_stuck(self, client):
        """Geen beweging na 5+ seconden geeft 'no_movement' via /current."""
        start_oefening(client)
        s = list(sessions.values())[0]

        update(client, 0)

        # Simuleer stilstand: zet last_change_time en last_received_time terug
        s["last_change_time"] -= 5.5
        s["last_received_time"] -= 5.5

        # Stuur zelfde state opnieuw (geen wissel → no_movement check)
        update(client, 0)

        res = current(client)
        assert res.json["status"] == "no_movement"

    def test_pi_disconnect_timeout(self, client):
        """Geen data van Pi voor 10+ seconden geeft 'error_piconnect' via /current."""
        start_oefening(client)
        s = list(sessions.values())[0]

        update(client, 0)

        # Simuleer 10.5 seconden geen data
        s["last_received_time"] -= 10.5

        res = current(client)
        assert res.json["status"] == "error_piconnect"

    def test_exercise_finished_flow(self, client):
        """15 volledige reps op goed tempo geeft status 'finished'."""
        start_oefening(client, oefening_id=1)
        s = list(sessions.values())[0]

        final_res = None
        for _ in range(15):
            # Naar boven (0 → 1)
            update(client, 0)
            s["last_change_time"] -= 2.1
            update(client, 1)
            s["has_hit_top"] = True

            # Naar beneden (1 → 0) — telt als rep
            s["last_change_time"] -= 2.1
            final_res = update(client, 0)

        assert final_res.json["current_feedback"] == "finished"
        assert final_res.json["counter"] == 15

    def test_calibration_happy_path(self, client):
        """Calibratie slaagt na CALIBRATION_DURATION seconden polsen in beeld."""
        client.post("/start_calibration")
        s = list(sessions.values())[0]

        # Eerste update: timer start
        client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})
        assert s["last_change_time"] is not None

        # Simuleer 5 seconden verstreken
        s["last_change_time"] -= 5.1

        res = client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})
        assert res.json["calibrated"] is True
        assert s["is_calibrated"] is True

    def test_calibration_onderbreking(self, client):
        """Timer reset als polsen uit beeld gaan."""
        client.post("/start_calibration")
        s = list(sessions.values())[0]

        # Start timer
        client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})
        s["last_change_time"] -= 3.0  # 3 seconden gevorderd

        # Onderbreking
        res = client.post("/update_status", json={"state": 0, "calibration_status": "not_calibrated"})
        assert res.json["status"] == "out_of_frame"
        assert s["last_change_time"] is None  # timer gereset

    def test_calibration_out_of_frame(self, client):
        """Nooit gecalibreerd als polsen altijd out_of_frame zijn."""
        client.post("/start_calibration")

        for _ in range(10):
            res = client.post("/update_status", json={"state": 0, "calibration_status": "not_calibrated"})
            assert res.json.get("calibrated") is not True

        s = list(sessions.values())[0]
        assert s["is_calibrated"] is False
