import requests
import time
import pytest
import allure

BASE_URL = "http://127.0.0.1:5000"

@allure.feature("FysioFit HerhalingsTeller & RitmeAnalyse")
class TestFysioFitLogic:

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        """Zorgt ervoor dat er voor elke test een schone oefening start (ID 1)."""
        with allure.step("Reset systeem en start Oefening 1 (Appels plukken)"):
            requests.post(f"{BASE_URL}/control_exercise", json={"oefening_id": 1, "actief": 1})
        yield
        with allure.step("Stop oefening na test"):
            requests.post(f"{BASE_URL}/control_exercise", json={"oefening_id": 0, "actief": 0})

    @allure.story("Tempo Validatie")
    @allure.title("Test Perfect Ritmische Beweging")
    @allure.description("Controleert of een herhaling binnen de 2-5 seconden correct wordt geteld.")
    def test_perfect_rep_tempo(self):
        with allure.step("Stuur startpositie: 0 (handen laag)"):
            requests.post(f"{BASE_URL}/update_status", json={"state": 0})

        with allure.step("Wacht 3 seconden (goed tempo) en stuur state 1"):
            time.sleep(3)
            res_up = requests.post(f"{BASE_URL}/update_status", json={"state": 1})
            assert res_up.json()["current_feedback"] == "ok"

        with allure.step("Wacht 3 seconden en voltooi de rep (terug naar state 0)"):
            time.sleep(3)
            res_down = requests.post(f"{BASE_URL}/update_status", json={"state": 0})
            
        with allure.step("Verifieer dat de teller op 1 staat en de status 'ok' is"):
            assert res_down.json()["counter"] == 1
            assert res_down.json()["current_feedback"] == "ok"

    @allure.story("Tempo Validatie")
    @allure.title("Test Te Snelle Beweging")
    @allure.description("Controleert of de status 'too_fast' wordt als de patiënt binnen 2 seconden beweegt.")
    def test_rep_too_fast(self):
        with allure.step("Stuur startpositie: 0"):
            requests.post(f"{BASE_URL}/update_status", json={"state": 0})

        with allure.step("Beweeg DIRECT (0.5s) naar state 1"):
            time.sleep(0.5)
            res = requests.post(f"{BASE_URL}/update_status", json={"state": 1})
            
        with allure.step("Verifieer feedback 'too_fast'"):
            assert res.json()["current_feedback"] == "too_fast"

    @allure.story("Tempo Validatie")
    @allure.title("Test Te Langzame Beweging")
    @allure.description("Controleert of de status 'too_slow' wordt als een beweging langer dan 5 seconden duurt.")
    def test_rep_too_slow(self):
        with allure.step("Stuur startpositie: 0"):
            requests.post(f"{BASE_URL}/update_status", json={"state": 0})

        with allure.step("Wacht 5.5 seconden en wissel naar state 1"):
            time.sleep(5.5)
            res = requests.post(f"{BASE_URL}/update_status", json={"state": 1})
            
        with allure.step("Verifieer feedback 'too_slow'"):
            assert res.json()["current_feedback"] == "too_slow"

    @allure.story("Foutafhandeling & Inactiviteit")
    @allure.title("Test Patiënt Staat Stil (Inactief)")
    @allure.description("Controleert of de server herkent wanneer de patiënt stopt met bewegen (geen state-wissel).")
    def test_patient_stuck(self):
        with allure.step("Stuur initiële state: 0"):
            requests.post(f"{BASE_URL}/update_status", json={"state": 0})
            
        with allure.step("Wacht 5.5 seconden zonder nieuwe state te sturen"):
            time.sleep(5.5)
            
        with allure.step("Vraag huidige status op via /current"):
            res = requests.get(f"{BASE_URL}/current")
            
        assert res.json()["status"] == "no_movement"

    @allure.story("Foutafhandeling & Inactiviteit")
    @allure.title("Test Pi 5 Verbindingsfout (Timeout)")
    @allure.description("Controleert of het dashboard in de 'error_piconnect' schiet als de Pi langer dan 10 seconden helemaal niks stuurt.")
    def test_pi_disconnect_timeout(self):
        with allure.step("Stuur eenmalig data"):
            requests.post(f"{BASE_URL}/update_status", json={"state": 0})
            
        with allure.step("Simuleer wegzakken verbinding door 10.5 seconden niks te sturen"):
            time.sleep(10.5)
            
        with allure.step("Controleer of het dashboard de error status overneemt"):
            res = requests.get(f"{BASE_URL}/current")
            
        assert res.json()["status"] == "error_piconnect"

    @allure.story("Doelstellingen")
    @allure.title("Test Oefening Voltooid (Finished)")
    @allure.description("Controleert of de status 'finished' wordt zodra het doel (bijv. 15 reps) is bereikt.")
    def test_exercise_finished_flow(self):
        with allure.step("Simuleer versneld de herhalingen tot vlak voor het doel"):
            # We zetten de counter handmatig omhoog in de test door loops te simuleren 
            # (In een echte unit test zou je de globale variabele mocken, maar we testen de HTTP flow)
            state = 0
            for _ in range(14): # Doe 14 volledige reps in een goed tempo (28 stappen)
                requests.post(f"{BASE_URL}/update_status", json={"state": state})
                state = 1 if state == 0 else 0
                time.sleep(2.1) # Net boven de 2 seconden grens
            
            # De 15e rep die de climax triggert
            requests.post(f"{BASE_URL}/update_status", json={"state": 1})
            time.sleep(2.1)
            final_res = requests.post(f"{BASE_URL}/update_status", json={"state": 0})

        with allure.step("Controleer of de status nu 'finished' is"):
            assert final_res.json()["current_feedback"] == "finished" or requests.get(f"{BASE_URL}/current").json()["status"] == "finished"