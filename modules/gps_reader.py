import serial
import pynmea2
import time
import threading
from datetime import datetime

GPS_PORT = "/dev/serial0"
GPS_BAUDRATE = 9600
GPS_TIMEOUT = 1.0

# Intervalles d'activation
GPS_ACTIVE_DURATION = 30   # 2 minutes
GPS_SLEEP_DURATION = 60#3600   # 60 minutes

# Dernière position valide
latest_position = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "satellites": 0,
    "timestamp": None,
    "fix": False
}

# Historique pour moyenne
position_history = []
position_lock = threading.Lock()


def parse_nmea_sentence(line):
    try:
        msg = pynmea2.parse(line)
        if isinstance(msg, pynmea2.types.talker.GGA):
            if msg.gps_qual > 0:  # gps_qual: 1 = GPS fix, 2 = DGPS fix
                return {
                    "latitude": msg.latitude,
                    "longitude": msg.longitude,
                    "altitude": float(msg.altitude),
                    "satellites": int(msg.num_sats),
                    "timestamp": datetime.utcnow(),
                    "fix": True
                }
    except pynmea2.nmea.ChecksumError:
        pass
    except Exception:
        pass
    return None


def gps_worker():
    global latest_position

    while True:
        print("[GPS] Début d'une nouvelle session d'acquisition...")
        try:
            with serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=GPS_TIMEOUT) as ser:
                start_time = time.time()
                while time.time() - start_time < GPS_ACTIVE_DURATION:
                    line = ser.readline().decode("ascii", errors="ignore").strip()
                    data = parse_nmea_sentence(line)
                    if data and data["fix"]:
                        with position_lock:
                            latest_position = data
                            position_history.append(data)
                            print(f"[GPS] Fix détecté : {data}")
        except Exception as e:
            print(f"[GPS] Erreur : {e}")
        print("[GPS] Fin de session, attente 30 minutes...")
        time.sleep(GPS_SLEEP_DURATION)


def get_gps_data():
    with position_lock:
        if not latest_position["fix"]:
            return {"error": "Pas de fix GPS"}
        
        return {
            "latitude": latest_position["latitude"],
            "longitude": latest_position["longitude"],
            "altitude": latest_position["altitude"],
            "satellites": latest_position["satellites"]
        }


def start_gps_loop():
    thread = threading.Thread(target=gps_worker, daemon=True)
    thread.start()
