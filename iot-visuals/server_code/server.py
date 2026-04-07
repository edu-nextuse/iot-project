from flask import Flask, render_template, request, jsonify 

app = Flask(__name__)

# Geef ze een standaardwaarde zodat de eerste 'fetch' niet faalt
last_status = "unknown"
last_temp = 0

@app.route("/temperature", methods=["POST"])
def temperature():
    global last_temp, last_status # Correcte variabelen
    
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
    return render_template("index.html")

@app.route("/current")
def current():
    # Dit stuurt de data naar je JavaScript
    return jsonify({
        "temp": last_temp,
        "status": last_status
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)