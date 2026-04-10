from flask import Flask, render_template, request, jsonify 

app = Flask(__name__)

# Geef ze een standaardwaarde zodat de eerste 'fetch' niet faalt
last_status = "unknown"
last_temp = 0
max_temp = 32
min_temp = 29

@app.route("/temperature", methods=["POST"])
def temperature():
    """
        Functie ontvangt data van de Pico, dit is temperatuur.
        Op basis van de temperatuur wordt er een status bepaald (ok, warning, carefull).
        Deze data wordt opgeslagen in globale variabelen zodat ze kunnen worden gebruikt in andere routes.
        Returnt een bevestiging dat de data is ontvangen.    
    """
    global last_temp, last_status
    
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    current_temp = data.get("temp")
    last_temp = current_temp

    # Initialiseer de response data
    response_data = {"received": True}

    # Logica bepalen
    if current_temp > max_temp:
        last_status = "warning"
        response_data.update({"warning": True}) # Rood aan, Groen uit
    elif current_temp < min_temp:
        last_status = "ok"
        response_data.update({"ok": True})      # Rood uit, Groen aan
    else:
        last_status = "carefull"
        response_data.update({"carefull": True}) # Rood aan, Groen aan

    print(f"Update ontvangen: {last_temp}°C status: {last_status}")
    return jsonify(response_data)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/buddy")
def buddy():
    return render_template("buddy.html")

@app.route("/current")
def current():
    # Dit stuurt de data naar je JavaScript
    return jsonify({
        "temp": last_temp,
        "status": last_status
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)