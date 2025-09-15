import serial
import pynmea2
import threading
import time
import os
from datetime import datetime

# ==============================
# Détection automatique du port
# ==============================
if os.path.exists("/dev/ttyACM0"):
    GPS_PORT = "/dev/ttyACM0"   # GPS USB (VK-162 par ex.)
elif os.path.exists("/dev/serial0"):
    GPS_PORT = "/dev/serial0"   # GPS UART GPIO (NEO-6M par ex.)
else:
    GPS_PORT = None             # Aucun GPS détecté

GPS_BAUDRATE = 9600
GPS_TIMEOUT = 1.0

# ==============================
# Données GPS partagées
# ==============================
gps_data = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "satellites": 0,
    "timestamp": None,
    "fix": False
}


def read_gps():
    """Boucle de lecture GPS (thread)."""
    global gps_data
    if GPS_PORT is None:
        print("[GPS ERROR] ❌ Aucun port GPS détecté")
        return

    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=GPS_TIMEOUT)
        print(f"[GPS] ✅ Boucle démarrée sur {GPS_PORT} à {GPS_BAUDRATE} bauds")

        for line in ser:
            try:
                line = line.decode("ascii", errors="replace").strip()
                if not line.startswith("$"):
                    continue
                # Debug brut
                # print("[GPS DEBUG] Trame brute:", line)

                msg = pynmea2.parse(line)

                # ==============================
                # GGA → fix, altitude, nb satellites
                # ==============================
                if isinstance(msg, pynmea2.types.talker.GGA):
                    gps_data.update({
                        "latitude": msg.latitude if msg.gps_qual > 0 else None,
                        "longitude": msg.longitude if msg.gps_qual > 0 else None,
                        "altitude": float(msg.altitude) if msg.altitude else None,
                        "satellites": int(msg.num_sats) if msg.num_sats else 0,
                        "timestamp": datetime.utcnow().isoformat(),
                        "fix": msg.gps_qual > 0
                    })
                    # print("[GPS DEBUG] maj GGA:", gps_data)

                # ==============================
                # RMC → fix + coordonnées
                # ==============================
                elif isinstance(msg, pynmea2.types.talker.RMC):
                    if msg.status == "A":  # Fix actif
                        gps_data.update({
                            "latitude": msg.latitude,
                            "longitude": msg.longitude,
                            "timestamp": datetime.utcnow().isoformat(),
                            "fix": True
                        })
                        # print("[GPS DEBUG] maj RMC:", gps_data)

            except Exception as e:
                print(f"[GPS ERROR] Parse: {e} | Trame: {line}")

    except Exception as e:
        print(f"[GPS ERROR] ❌ Impossible d’ouvrir {GPS_PORT}: {e}")


def start_gps_loop():
    """Lancer la boucle GPS dans un thread."""
    t = threading.Thread(target=read_gps, daemon=True)
    t.start()
    print("[GPS] Thread lancé")


def get_gps_data():
    """Retourner les dernières données GPS connues."""
    return gps_data.copy()


if __name__ == "__main__":
    start_gps_loop()
    while True:
        print(get_gps_data())
        time.sleep(2)
