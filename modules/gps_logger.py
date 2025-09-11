# modules/gps_logger.py
import csv
import pathlib
import datetime
import time
from modules.gps_reader import get_gps_data

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def log_loop(interval=30):
    """Écrit une ligne GPS toutes les X secondes (même sans fix)."""
    while True:
        data = get_gps_data() or {}
        path = LOG_DIR / f"gps_{datetime.date.today()}.csv"
        newfile = not path.exists()

        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if newfile:
                w.writerow(["timestamp_utc", "latitude", "longitude", "altitude", "sats", "fix"])

            w.writerow([
                datetime.datetime.utcnow().isoformat(),
                data.get("latitude"),
                data.get("longitude"),
                data.get("altitude"),
                data.get("satellites"),
                data.get("fix"),
            ])

        print(f"[GPS_LOGGER] Ligne écrite : {data}")
        time.sleep(interval)

if __name__ == "__main__":
    print("[GPS_LOGGER] Démarrage en mode test (intervalle = 5s)")
    log_loop(5)
