# modules/gps_reader.py
import serial
import pynmea2
import threading
import time
import os
from datetime import datetime

if os.path.exists("/dev/ttyACM0"):
    GPS_PORT = "/dev/ttyACM0"   # VK-162 USB
elif os.path.exists("/dev/serial0"):
    GPS_PORT = "/dev/serial0"   # Neo via UART GPIO
else:
    GPS_PORT = None

GPS_BAUDRATE = 9600
GPS_TIMEOUT = 1.0

gps_data = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "satellites": 0,
    "timestamp": None,
    "fix": False
}

gps_thread = None  # pour éviter plusieurs threads

def read_gps():
    """Boucle de lecture GPS en thread."""
    global gps_data
    if GPS_PORT is None:
        print("[GPS ERROR] Aucun port GPS détecté")
        return

    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=GPS_TIMEOUT)
        print(f"[GPS] Boucle démarrée sur {GPS_PORT} à {GPS_BAUDRATE} bauds")

        for line in ser:
            try:
                line = line.decode("ascii", errors="replace").strip()
                if not line.startswith("$"):
                    continue

                msg = pynmea2.parse(line)

                if isinstance(msg, pynmea2.types.talker.GGA):
                    gps_data.update({
                        "latitude": msg.latitude if msg.gps_qual > 0 else None,
                        "longitude": msg.longitude if msg.gps_qual > 0 else None,
                        "altitude": float(msg.altitude) if msg.altitude else None,
                        "satellites": int(msg.num_sats) if msg.num_sats else 0,
                        "timestamp": datetime.utcnow().isoformat(),
                        "fix": msg.gps_qual > 0
                    })

                elif isinstance(msg, pynmea2.types.talker.RMC):
                    if msg.status == "A":  # Fix actif
                        gps_data.update({
                            "latitude": msg.latitude,
                            "longitude": msg.longitude,
                            "timestamp": datetime.utcnow().isoformat(),
                            "fix": True
                        })

            except Exception as e:
                print("[GPS ERROR] Parse:", e, line)

    except Exception as e:
        print("[GPS ERROR] Impossible d'ouvrir le port:", e)


def start_gps_loop():
    """Lancer la boucle GPS dans un seul thread."""
    global gps_thread
    if gps_thread is None or not gps_thread.is_alive():
        gps_thread = threading.Thread(target=read_gps, daemon=True)
        gps_thread.start()
        print("[GPS] Thread lancé")


def get_gps_data():
    """Retourner les dernières données GPS connues."""
    return gps_data.copy()


if __name__ == "__main__":
    start_gps_loop()
    while True:
        print(get_gps_data())
        time.sleep(2)
