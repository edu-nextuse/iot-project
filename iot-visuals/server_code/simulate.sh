#!/bin/bash

URL="http://127.0.0.1:5000/update_status"
REPS=20

echo "=================================================="
echo "  START SIMULATIE: $REPS herhalingen (2s interval)"
echo "=================================================="
echo "Zorg dat je eerst een oefening start in het portaal!"
echo ""

for ((i=1; i<=REPS; i++))
do
    echo "--- Herhaling $i/$REPS ---"
    
    # 1. Stuur State 1 (Handen HOOG)
    echo "[$(date +%H:%M:%S)] Stuur state: 1 (Handen HOOG)"
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 1}'
    echo "" # Nieuwe regel voor de overzichtelijkheid
    
    # Wacht 2 seconden
    sleep 2

    # 2. Stuur State 0 (Handen LAAG)
    echo "[$(date +%H:%M:%S)] Stuur state: 0 (Handen LAAG)"
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 0}'
    echo ""
    
    # Wacht weer 2 seconden voor de volgende rep begint
    sleep 2
done

echo "=================================================="
echo "  SIMULATIE AFGEROND!"
echo "=================================================="