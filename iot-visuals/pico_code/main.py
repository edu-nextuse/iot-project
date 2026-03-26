from time import sleep
from machine import Pin, ADC
from boot import connection
import urequests as requests # Cleaned import
import config

# 1. Configuraties van de pinnen
led_red = Pin(15, Pin.OUT)
led_green = Pin(16, Pin.OUT)
# Initialiseer de interne LED voor "Activity"
led_activity = Pin("LED", Pin.OUT) 

sensor = ADC(26)

# Berekeningsfactor
conversion_factor = 3.3 / 65535

url = f"http://{config.SERVER}:{config.PORT}{config.ENDPOINT}"

while connection.isconnected():
    # 1. Meting doen
    reading = sensor.read_u16()
    temp = round((reading * conversion_factor * 100) - 50, 2)
    
    payload = {"temp": temp}
    print(f"Versturen naar server: {temp}°C...")
    
    try:
        # --- ACTIVITEIT START ---
        led_activity.on() 
        
        # 3. HTTP POST verzoek versturen
        response = requests.post(url, json=payload)
        
        # --- ACTIVITEIT STOP ---
        led_activity.off()

        answer = response.json()
        
        # 4. Actie ondernemen op basis van het antwoord
        if answer.get("warning") and answer.get("almost"):
            led_red.on()
            led_green.on()
        elif answer.get("warning") and answer.get("almost") == False:
            led_red.on()
            led_green.off()
        else:
            led_red.off()
            led_green.on()
            
        response.close()
        
    except Exception as e:
        led_activity.off() # Zorg dat de LED uitgaat bij een fout
        print("Fout bij verbinden:", e)

    sleep(2)
