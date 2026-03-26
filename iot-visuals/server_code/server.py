from flask import Flask, request, jsonify
from display_manager import visuals 

app = Flask(__name__)

@app.route("/temperature", methods=["POST"])
def temperature():
    """Het endpoint dat de metingen ontvangt"""
    data = request.json
    current_temp = data.get("temp")
    
    print(f"Ontvangen temperatuur: {current_temp}°C")

    # De logica: we bepalen hier of er een waarschuwing moet zijn
    if current_temp > 20:
        visuals.show_warning()
        response_data = {
            "status": "warning",
            "message": "Te warm!",
            "warning": True,
            "almost": False
        }
    elif current_temp < 17:
        visuals.show_ok()
        response_data = {
            "status": "ok",
            "message": "Temperatuur is prima.",
            "warning": False,
            "almost": False
        }
    else:
        visuals.show_carefull()
        response_data = {
            "status": "carefull",
            "message": "Temperatuur is aan de warme kant.",
            "warning": True,
            "almost": True
        }

    return jsonify(response_data)

if __name__ == "__main__":
    # Host 0.0.0.0 zorgt dat de Pico verbinding kan maken via je netwerk
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)