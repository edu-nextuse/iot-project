#!/bin/bash

URL="http://127.0.0.1:5000/update_status"
BASE_URL="http://127.0.0.1:5000"

echo "=================================================="
echo "  CALIBRATIE TEST"
echo "=================================================="
echo ""

# -----------------------------------------------
# TEST 1: Happy path — calibrated blijft staan
# -----------------------------------------------
echo "Reset + start calibratie op server..."
curl -s -X POST "$BASE_URL/reset_calibration"
echo ""
curl -s -X POST "$BASE_URL/start_calibration"
echo ""
sleep 1

echo "TEST 1: Happy path (calibrated 12x sturen, 0.5s interval = ~6s)"
echo "Verwacht: eindigt met status 'calibrated: true'"
echo ""

for ((i=1; i<=12; i++))
do
    echo -n "[$(date +%H:%M:%S)] Poging $i — stuur calibrated: "
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 0, "calibration_status": "calibrated"}'
    echo ""
    sleep 0.5
done

echo ""
echo "--- TEST 1 KLAAR ---"
echo ""
sleep 2

# -----------------------------------------------
# TEST 2: Reset test — not_calibrated tussendoor
# -----------------------------------------------
echo "Reset + start calibratie op server..."
curl -s -X POST "$BASE_URL/reset_calibration"
echo ""
curl -s -X POST "$BASE_URL/start_calibration"
echo ""
sleep 1

echo "TEST 2: Reset test (calibrated 4x, dan not_calibrated, dan calibrated 12x)"
echo "Verwacht: timer reset na not_calibrated, daarna alsnog 'calibrated: true'"
echo ""

for ((i=1; i<=4; i++))
do
    echo -n "[$(date +%H:%M:%S)] Poging $i — stuur calibrated: "
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 0, "calibration_status": "calibrated"}'
    echo ""
    sleep 0.5
done

echo -n "[$(date +%H:%M:%S)] Stuur not_calibrated (onderbreking): "
curl -s -X POST "$URL" \
     -H "Content-Type: application/json" \
     -d '{"state": 0, "calibration_status": "not_calibrated"}'
echo ""
echo "Timer zou nu gereset moeten zijn."
sleep 0.5

for ((i=1; i<=12; i++))
do
    echo -n "[$(date +%H:%M:%S)] Poging $i na reset — stuur calibrated: "
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 0, "calibration_status": "calibrated"}'
    echo ""
    sleep 0.5
done

echo ""
echo "--- TEST 2 KLAAR ---"
echo ""
sleep 2

# -----------------------------------------------
# TEST 3: Out of frame — alleen not_calibrated
# -----------------------------------------------
echo "Reset + start calibratie op server..."
curl -s -X POST "$BASE_URL/reset_calibration"
echo ""
curl -s -X POST "$BASE_URL/start_calibration"
echo ""
sleep 1

echo "TEST 3: Out of frame (not_calibrated 6x sturen)"
echo "Verwacht: altijd status 'out_of_frame' terug"
echo ""

for ((i=1; i<=6; i++))
do
    echo -n "[$(date +%H:%M:%S)] Poging $i — stuur not_calibrated: "
    curl -s -X POST "$URL" \
         -H "Content-Type: application/json" \
         -d '{"state": 0, "calibration_status": "not_calibrated"}'
    echo ""
    sleep 0.5
done

echo ""
echo "--- TEST 3 KLAAR ---"
echo ""
echo "=================================================="
echo "  ALLE TESTS AFGEROND"
echo "=================================================="