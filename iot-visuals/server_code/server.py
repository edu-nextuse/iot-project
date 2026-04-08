from flask import Flask, render_template, request, jsonify 

app = Flask(__name__)

# Geef ze een standaardwaarde zodat de eerste 'fetch' niet faalt
last_status = "unknown"
last_temp = 0

@app.route("/temperature", methods=["POST"])
def temperature():
    """
        Functie ontvangt data van de Pico, dit is temperatuur.
        Op basis van de temperatuur wordt er een status bepaald (ok, warning, carefull).
        Deze data wordt opgeslagen in globale variabelen zodat ze kunnen worden gebruikt in andere routes.
        Returnt een bevestiging dat de data is ontvangen.    
    """
    global last_temp, last_status # Deze zijn global zodat we ze kunnen updaten en gebruiken in andere routes
    
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    current_temp = data.get("temp")
    last_temp = current_temp

    # Logica bepalen
    if current_temp > 20:
        last_status = "warning"
    elif current_temp < 17:
        last_status = "ok"
    else:
        last_status = "carefull"

    print(f"Update ontvangen: {last_temp}°C status: {last_status}")
    return jsonify({"received": True})

@app.route("/")
def index():
    # Dit is de homepage waar temp en status worden weergegeven
    return render_template("index.html")

@app.route("/buddy")
def buddy():
    # Dit is de pagina waar de buddy zich bevindt, deze zal ook de data van de status gebruiken
    return render_template("buddy.html")

@app.route("/current")
def current():
    # Dit stuurt de data naar de JavaScript waar buddy.html & index.html deze kunnen gebruiken
    return jsonify({
        "temp": last_temp,
        "status": last_status
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)