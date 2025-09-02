import serial
import time
import threading
from datetime import datetime, timedelta
import pynmea2

# Paramètres du port série
SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 9600

# Durée et intervalle d'acquisition
ACQUISITION_DURATION = timedelta(minutes=2)
ACQUISITION_INTERVAL = timedelta(minutes=30)

# Dernier GPS moyen
latest_position = {"latitude": None, "longitude": None, "altitude": None, "satellites": 0, "timestamp": None, "error": "Pas encore de données"}

# État d'acquisition
_last_acquisition = datetime.min
_acquiring = False
_thread_started = False


def _gps_background_task():
    global _last_acquisition, _acquiring, latest_position

    while True:
        now = datetime.now()
        if not _acquiring and (now - _last_acquisition >= ACQUISITION_INTERVAL):
            _acquiring = True
            _last_acquisition = now

            print("[GPS] Début d'une nouvelle session d'acquisition...")

            try:
                with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                    start_time = datetime.now()
                    positions = []
                    satellites = 0

                    while datetime.now() - start_time < ACQUISITION_DURATION:
                        line = ser.readline().decode(errors="ignore").strip()
                        if line.startswith("$GPGGA"):
                            try:
                                msg = pynmea2.parse(line)
                                if int(msg.gps_qual) > 0:
                                    lat = msg.latitude
                                    lon = msg.longitude
                                    alt = float(msg.altitude)
                                    sats = int(msg.num_sats)
                                    positions.append((lat, lon, alt, sats))
                            except:
                                continue

                    if positions:
                        avg_lat = sum(p[0] for p in positions) / len(positions)
                        avg_lon = sum(p[1] for p in positions) / len(positions)
                        avg_alt = round(sum(p[2] for p in positions) / len(positions), 1)
                        avg_sats = round(sum(p[3] for p in positions) / len(positions))

                        latest_position = {
                            "latitude": round(avg_lat, 6),
                            "longitude": round(avg_lon, 6),
                            "altitude": avg_alt,
                            "satellites": avg_sats,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        print(f"[GPS] Position moyenne captée : {latest_position}")
                    else:
                        latest_position = {"error": "Aucune position valide captée"}
                        print("[GPS] Aucune trame valide avec fix.")

            except Exception as e:
                latest_position = {"error": f"Erreur série : {e}"}
                print(f"[GPS] Erreur : {e}")

            _acquiring = False

        time.sleep(5)  # vérifier toutes les 5 secondes si c'est l'heure


def get_gps_data():
    global _thread_started
    if not _thread_started:
        threading.Thread(target=_gps_background_task, daemon=True).start()
        _thread_started = True
    return latest_position
