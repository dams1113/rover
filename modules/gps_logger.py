# modules/gps_logger.py
import csv
import pathlib
import datetime
import time
from modules.gps_reader import get_gps_data

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def log_loop(interval=30):
    """Écrit une ligne GPS (fix ou non) dans logs/gps_YYYY-MM-DD.csv"""
    while True:
        data = get_gps_data() or {}

        lat = data.get("latitude")
        lon = data.get("longitude")

        if lat is None or lon is None:
            print("[GPS_LOGGER] Pas de coordonnées valides, ligne ignorée")
            time.sleep(interval)
            continue

        path = LOG_DIR / f"gps_{datetime.date.today()}.csv"
        newfile = not path.exists()

        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if newfile:
                w.writerow(["timestamp_utc", "latitude", "longitude", "altitude", "sats", "fix"])

            w.writerow([
                datetime.datetime.utcnow().isoformat(),
                lat,
                lon,
                data.get("altitude"),
                data.get("satellites"),
                data.get("fix"),
            ])

        status = "FIX" if data.get("fix") else "NOFIX"
        print(f"[GPS_LOGGER] ({status}) Ligne écrite : {lat}, {lon}, sats={data.get('satellites')}")

        time.sleep(interval)


if __name__ == "__main__":
    print("[GPS_LOGGER] Démarrage en mode test (intervalle = 5s)")
    log_loop(5)
