import serial
import pynmea2
import threading
import time
from datetime import datetime

# Paramètres du port série
GPS_PORT = "/dev/serial0"
GPS_BAUDRATE = 9600
GPS_TIMEOUT = 1.0

# Dernière position connue (thread-safe)
latest_position = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "satellites": 0,
    "timestamp": None,
    "fix": False
}
_position_lock = threading.Lock()


def parse_nmea_sentence(line):
    """Parse une trame NMEA et met à jour latest_position si valide"""
    global latest_position

    try:
        msg = pynmea2.parse(line)
    except pynmea2.ParseError:
        return

    if isinstance(msg, pynmea2.types.talker.GGA):
        with _position_lock:
            # Fix : gps_qual >= 1 (1 = GPS fix, 2 = DGPS, etc.)
            fix_ok = int(msg.gps_qual or 0) >= 1
            latest_position.update({
                "latitude": msg.latitude if fix_ok else None,
                "longitude": msg.longitude if fix_ok else None,
                "altitude": float(msg.altitude) if fix_ok and msg.altitude else None,
                "satellites": int(msg.num_sats or 0),
                "timestamp": datetime.utcnow().isoformat(),
                "fix": fix_ok
            })


def gps_loop():
    """Boucle de lecture GPS en tâche de fond"""
    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=GPS_TIMEOUT)
    except Exception as e:
        print(f"[GPS ERROR] Impossible d'ouvrir {GPS_PORT}: {e}")
        return

    print("[GPS] Boucle démarrée")
    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if line.startswith("$"):
                parse_nmea_sentence(line)
        except Exception as e:
            print(f"[GPS ERROR] {e}")
        time.sleep(0.1)


def start_gps_loop():
    """Démarre gps_loop() dans un thread"""
    t = threading.Thread(target=gps_loop, daemon=True)
    t.start()
    return t


def get_gps_data():
    """Retourne une copie de la dernière position connue"""
    with _position_lock:
        return latest_position.copy()


# Mode test (lancer directement ce fichier)
if __name__ == "__main__":
    start_gps_loop()
    for _ in range(20):
        print(get_gps_data())
        time.sleep(1)
