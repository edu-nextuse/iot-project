import pytest
import sys
import os
import time
import allure

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "iot-visuals", "server_code"))

from server import app, init_db, sessions

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    """Flask test client met schone database en sessie."""
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"

    with app.test_client() as client:
        with app.app_context():
            init_db()
        sessions.clear()
        yield client
        sessions.clear()

def start_oefening(client, oefening_id=1):
    """Log in en start een oefening."""
    client.post("/register", data={
        "name": "Test",
        "email": "test@test.nl",
        "password": "test123"
    })
    client.post("/login", data={
        "email": "test@test.nl",
        "password": "test123"
    })
    client.post("/set_system", json={"online": True})
    client.post("/start_calibration")
    s = list(sessions.values())[0]
    s["is_calibrated"] = True
    s["calibration_active"] = False
    client.post("/control_exercise", json={"oefening_id": oefening_id, "actief": 1})

def update(client, state):
    return client.post("/update_status", json={
        "state": state,
        "calibration_status": "not_calibrated"
    })

def current(client):
    return client.get("/current")

# ── Tests ─────────────────────────────────────────────────────────────────────

@allure.feature("FysioFit HerhalingsTeller & RitmeAnalyse")
class TestFysioFitLogic:

    # ── Tempo Validatie ───────────────────────────────────────────────────────

    @allure.story("Tempo Validatie")
    @allure.title("Test Perfect Ritmische Beweging")
    @allure.description("Controleert of een herhaling binnen de 1-5 seconden correct wordt geteld.")
    def test_perfect_rep_tempo(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0 (handen laag)"):
            update(client, 0)

        with allure.step("Simuleer 3 seconden en stuur state 1 (handen omhoog)"):
            s["last_change_time"] -= 3.0
            res_up = update(client, 1)
            assert res_up.json["current_feedback"] == "ok"

        with allure.step("Simuleer nog 3 seconden en voltooi de rep (terug naar state 0)"):
            s["last_change_time"] -= 3.0
            res_down = update(client, 0)

        with allure.step("Verifieer dat de teller op 1 staat en de status 'ok' is"):
            assert res_down.json["counter"] == 1
            assert res_down.json["current_feedback"] == "ok"

    @allure.story("Tempo Validatie")
    @allure.title("Test Te Snelle Beweging")
    @allure.description("Controleert of de status 'too_fast' wordt als de patiënt binnen 1 seconde beweegt.")
    def test_rep_too_fast(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0"):
            update(client, 0)

        with allure.step("Simuleer 0.5 seconden en stuur state 1"):
            s["last_change_time"] -= 0.5
            res = update(client, 1)

        with allure.step("Verifieer feedback 'too_fast'"):
            assert res.json["current_feedback"] == "too_fast"

    @allure.story("Tempo Validatie")
    @allure.title("Test Te Langzame Beweging")
    @allure.description("Controleert of de status 'too_slow' wordt als een beweging langer dan 5 seconden duurt.")
    def test_rep_too_slow(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0"):
            update(client, 0)

        with allure.step("Simuleer 5.5 seconden en wissel naar state 1"):
            s["last_change_time"] -= 5.5
            res = update(client, 1)

        with allure.step("Verifieer feedback 'too_slow'"):
            assert res.json["current_feedback"] == "too_slow"

    @allure.story("Tempo Validatie")
    @allure.title("Grenswaarde: Beweging Precies op MIN_FREQ (1.0s)")
    @allure.description("Een beweging van exact 1.0 seconde valt op de grens en is 'ok' (niet < MIN_FREQ).")
    def test_rep_exact_min_freq(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0"):
            update(client, 0)

        with allure.step("Simuleer exact 1.0 seconde"):
            s["last_change_time"] -= 1.0
            res = update(client, 1)

        with allure.step("Verifieer feedback — exact op grens is 'ok' (duration == MIN_FREQ, niet < MIN_FREQ)"):
            assert res.json["current_feedback"] == "ok"

    @allure.story("Tempo Validatie")
    @allure.title("Grenswaarde: Beweging Precies op MAX_FREQ (5.0s)")
    @allure.description("Een beweging van exact 5.0 seconde valt op de grens en is 'too_slow' (niet > MAX_FREQ).")
    def test_rep_exact_max_freq(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0"):
            update(client, 0)

        with allure.step("Simuleer exact 5.0 seconden"):
            s["last_change_time"] -= 5.0
            res = update(client, 1)

        with allure.step("Verifieer feedback — exact op grens is 'too_slow' (duration == MAX_FREQ)"):
            assert res.json["current_feedback"] == "too_slow"

    @allure.story("Tempo Validatie")
    @allure.title("Grenswaarde: Beweging Net Binnen Goed Tempo (1.1s)")
    @allure.description("Een beweging van 1.1 seconde moet als 'ok' worden beschouwd.")
    def test_rep_just_above_min_freq(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur startpositie: 0"):
            update(client, 0)

        with allure.step("Simuleer 1.1 seconden"):
            s["last_change_time"] -= 1.1
            res = update(client, 1)

        with allure.step("Verifieer feedback 'ok'"):
            assert res.json["current_feedback"] == "ok"

    # ── Rep Telling ───────────────────────────────────────────────────────────

    @allure.story("Rep Telling")
    @allure.title("Rep Telt Niet Zonder has_hit_top (0→0 zonder 1)")
    @allure.description("Een rep mag alleen tellen als state 1 (omhoog) bereikt is geweest.")
    def test_rep_zonder_top(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur 0, dan direct weer 0 zonder 1 tussendoor"):
            update(client, 0)
            s["last_change_time"] -= 2.1
            update(client, 1)
            s["has_hit_top"] = False  # forceer geen top bereikt
            s["last_change_time"] -= 2.1
            res = update(client, 0)

        with allure.step("Verifieer dat teller nog op 0 staat"):
            assert res.json["counter"] == 0

    @allure.story("Rep Telling")
    @allure.title("Rep Na Finished Telt Niet Meer")
    @allure.description("Na het bereiken van het doel mogen extra reps de teller niet verhogen.")
    def test_rep_na_finished(self, client):
        start_oefening(client, oefening_id=1)
        s = list(sessions.values())[0]

        with allure.step("Voltooi 15 reps"):
            for _ in range(15):
                update(client, 0)
                s["last_change_time"] -= 2.1
                update(client, 1)
                s["has_hit_top"] = True
                s["last_change_time"] -= 2.1
                update(client, 0)

        with allure.step("Probeer nog een extra rep"):
            update(client, 1)
            s["last_change_time"] -= 2.1
            update(client, 0)

        with allure.step("Verifieer teller nog steeds 15 en status 'finished'"):
            assert s["rep_counter"] == 15
            assert s["last_status"] == "finished"

    # ── Doelstellingen ────────────────────────────────────────────────────────

    @allure.story("Doelstellingen")
    @allure.title("Test Oefening 1 Voltooid (Appels plukken — 15 reps)")
    @allure.description("Controleert of de status 'finished' wordt zodra het doel van 15 reps bereikt is.")
    def test_exercise_finished_flow(self, client):
        start_oefening(client, oefening_id=1)
        s = list(sessions.values())[0]

        with allure.step("Simuleer 15 volledige herhalingen op goed tempo"):
            final_res = None
            for _ in range(15):
                update(client, 0)
                s["last_change_time"] -= 2.1
                update(client, 1)
                s["has_hit_top"] = True
                s["last_change_time"] -= 2.1
                final_res = update(client, 0)

        with allure.step("Controleer of de status nu 'finished' is"):
            assert final_res.json["current_feedback"] == "finished"

        with allure.step("Controleer of de teller op 15 staat"):
            assert final_res.json["counter"] == 15

    @allure.story("Doelstellingen")
    @allure.title("Test Oefening 2 Voltooid (Doekje vegen — 20 reps)")
    @allure.description("Controleert of de status 'finished' wordt bij 20 reps voor oefening 2.")
    def test_exercise_2_finished_flow(self, client):
        start_oefening(client, oefening_id=2)
        s = list(sessions.values())[0]

        with allure.step("Simuleer 20 volledige herhalingen op goed tempo"):
            final_res = None
            for _ in range(20):
                update(client, 0)
                s["last_change_time"] -= 2.1
                update(client, 1)
                s["has_hit_top"] = True
                s["last_change_time"] -= 2.1
                final_res = update(client, 0)

        with allure.step("Controleer of de status 'finished' is"):
            assert final_res.json["current_feedback"] == "finished"

        with allure.step("Controleer of de teller op 20 staat"):
            assert final_res.json["counter"] == 20

    # ── Sessie & State ────────────────────────────────────────────────────────

    @allure.story("Sessie & State")
    @allure.title("State Update Genegeerd Als Oefening Niet Actief")
    @allure.description("States mogen niet verwerkt worden als actief=0.")
    def test_update_genegeerd_bij_inactief(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]
        s["current_task"]["actief"] = 0

        with allure.step("Stuur state update terwijl oefening niet actief is"):
            res = update(client, 1)

        with allure.step("Verifieer dat de update genegeerd wordt"):
            assert res.json["status"] == "ignored"

    @allure.story("Sessie & State")
    @allure.title("Current Zonder State Update")
    @allure.description("Controleer dat /current werkt zonder dat er ooit een state gestuurd is.")
    def test_current_zonder_state(self, client):
        start_oefening(client)

        with allure.step("Vraag /current op zonder update gestuurd te hebben"):
            res = current(client)

        with allure.step("Verifieer dat de response geldig is"):
            assert "status" in res.json
            assert "counter" in res.json
            assert "target" in res.json

    # ── Foutafhandeling & Inactiviteit ────────────────────────────────────────

    @allure.story("Foutafhandeling & Inactiviteit")
    @allure.title("Test Patiënt Staat Stil (Inactief)")
    @allure.description("Controleert of de server herkent wanneer de patiënt stopt met bewegen.")
    def test_patient_stuck(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur initiële state: 0"):
            update(client, 0)

        with allure.step("Simuleer 5.5 seconden stilstand"):
            s["last_change_time"] -= 5.5
            s["last_received_time"] -= 5.5
            update(client, 0)

        with allure.step("Vraag huidige status op via /current"):
            res = current(client)

        with allure.step("Verifieer status 'no_movement'"):
            assert res.json["status"] == "no_movement"

    @allure.story("Foutafhandeling & Inactiviteit")
    @allure.title("Test Pi Verbindingsfout (Timeout)")
    @allure.description("Controleert of het dashboard 'error_piconnect' toont als de Pi langer dan 10 seconden niks stuurt.")
    def test_pi_disconnect_timeout(self, client):
        start_oefening(client)
        s = list(sessions.values())[0]

        with allure.step("Stuur data zodat last_received_time gezet wordt"):
            update(client, 0)
            s["last_change_time"] -= 2.1
            update(client, 1)

        with allure.step("Simuleer 10.5 seconden geen verbinding"):
            s["last_received_time"] = time.time() - 10.5

        with allure.step("Controleer of het dashboard de error status toont"):
            res = current(client)

        with allure.step("Verifieer status 'error_piconnect'"):
            assert res.json["status"] == "error_piconnect"

    # ── Error Endpoint ────────────────────────────────────────────────────────

    @allure.story("Error Endpoint")
    @allure.title("Test Pi Error Opslaan en Ophalen")
    @allure.description("Controleert of een Pi-error correct opgeslagen en teruggestuurd wordt.")
    def test_error_opslaan_ophalen(self, client):
        with allure.step("Stuur een Pi-error"):
            res = client.post("/error", json={"error": "YOLO model crashed"})
            assert res.json["status"] == "ok"

        with allure.step("Haal de error op"):
            res = client.get("/error")

        with allure.step("Verifieer het bericht en timestamp"):
            assert res.json["message"] == "YOLO model crashed"
            assert "time" in res.json

    @allure.story("Error Endpoint")
    @allure.title("Test Meest Recente Error Overschrijft Vorige")
    @allure.description("Bij meerdere errors moet altijd de laatste zichtbaar zijn.")
    def test_error_overschrijven(self, client):
        with allure.step("Stuur twee errors achter elkaar"):
            client.post("/error", json={"error": "Eerste fout"})
            client.post("/error", json={"error": "Tweede fout"})

        with allure.step("Verifieer dat de tweede error zichtbaar is"):
            res = client.get("/error")
            assert res.json["message"] == "Tweede fout"

    @allure.story("Error Endpoint")
    @allure.title("Test Lege Error State")
    @allure.description("Controleert dat een lege error state terugkomt als er geen error is.")
    def test_error_leeg(self, client):
        with allure.step("Haal error op zonder dat er een gestuurd is"):
            res = client.get("/error")

        with allure.step("Verifieer lege state"):
            assert res.json == {} or res.json.get("message") is None

    # ── Keypoints ─────────────────────────────────────────────────────────────

    @allure.story("Keypoints")
    @allure.title("Test Keypoints Opslaan en Ophalen")
    @allure.description("Controleert of keypoints correct opgeslagen en teruggestuurd worden.")
    def test_keypoints_opslaan_ophalen(self, client):
        kp = {
            "nose": [320, 80],
            "left_wrist": [210, 50],
            "right_wrist": [430, 50]
        }

        with allure.step("POST keypoints naar /keypoints"):
            res = client.post("/keypoints", json={
                "timestamp": 1234567890.0,
                "keypoints": kp
            })
            assert res.json["status"] == "ok"

        with allure.step("GET keypoints van /keypoints"):
            res = client.get("/keypoints")

        with allure.step("Verifieer dat de keypoints correct teruggegeven worden"):
            assert res.json["nose"] == [320, 80]
            assert res.json["left_wrist"] == [210, 50]
            assert res.json["right_wrist"] == [430, 50]

    @allure.story("Keypoints")
    @allure.title("Test Lege Keypoints")
    @allure.description("Controleert dat lege keypoints {} correct terugkomen.")
    def test_keypoints_leeg(self, client):
        with allure.step("GET keypoints zonder dat er iets gestuurd is"):
            res = client.get("/keypoints")

        with allure.step("Verifieer lege response"):
            assert res.json == {}

    @allure.story("Keypoints")
    @allure.title("Test Keypoints Worden Overschreven")
    @allure.description("Nieuwe keypoints overschrijven de vorige.")
    def test_keypoints_overschrijven(self, client):
        with allure.step("Stuur eerste keypoints"):
            client.post("/keypoints", json={
                "timestamp": 1.0,
                "keypoints": {"nose": [100, 100]}
            })

        with allure.step("Stuur nieuwe keypoints"):
            client.post("/keypoints", json={
                "timestamp": 2.0,
                "keypoints": {"nose": [200, 200]}
            })

        with allure.step("Verifieer dat de nieuwe keypoints zichtbaar zijn"):
            res = client.get("/keypoints")
            assert res.json["nose"] == [200, 200]

    # ── Calibratie ────────────────────────────────────────────────────────────

    @allure.story("Calibratie")
    @allure.title("Test Calibratie Happy Path")
    @allure.description("Calibratie slaagt na CALIBRATION_DURATION seconden polsen in beeld.")
    def test_calibration_happy_path(self, client):
        with allure.step("Start calibratie"):
            client.post("/start_calibration")
            s = list(sessions.values())[0]

        with allure.step("Stuur eerste calibrated update — timer start"):
            client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})
            assert s["last_change_time"] is not None

        with allure.step("Simuleer 5.1 seconden verstreken"):
            s["last_change_time"] = time.time() - 5.1

        with allure.step("Stuur tweede update — calibratie moet slagen"):
            res = client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})

        with allure.step("Verifieer calibrated: True"):
            assert res.json["calibrated"] is True
            assert s["is_calibrated"] is True

    @allure.story("Calibratie")
    @allure.title("Test Calibratie Onderbreking")
    @allure.description("Timer reset als polsen uit beeld verdwijnen.")
    def test_calibration_onderbreking(self, client):
        with allure.step("Start calibratie en laat timer 3 seconden lopen"):
            client.post("/start_calibration")
            s = list(sessions.values())[0]
            client.post("/update_status", json={"state": 0, "calibration_status": "calibrated"})
            s["last_change_time"] = time.time() - 3.0

        with allure.step("Polsen verdwijnen uit beeld"):
            res = client.post("/update_status", json={"state": 0, "calibration_status": "not_calibrated"})

        with allure.step("Verifieer out_of_frame en timer gereset"):
            assert res.json["status"] == "out_of_frame"
            assert s["last_change_time"] is None

    @allure.story("Calibratie")
    @allure.title("Test Calibratie Out of Frame")
    @allure.description("Nooit gecalibreerd als polsen altijd buiten beeld zijn.")
    def test_calibration_out_of_frame(self, client):
        with allure.step("Start calibratie"):
            client.post("/start_calibration")

        with allure.step("Stuur 10x not_calibrated"):
            for _ in range(10):
                res = client.post("/update_status", json={"state": 0, "calibration_status": "not_calibrated"})
                assert res.json.get("calibrated") is not True

        with allure.step("Verifieer is_calibrated False"):
            s = list(sessions.values())[0]
            assert s["is_calibrated"] is False
