import csv
import pathlib
import datetime
import time
from modules.gps_reader import get_gps_data, start_gps_loop

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def log_loop(interval=30):
    """Écrit la position toutes les X secondes dans logs/gps_YYYY-MM-DD.csv (seulement si fix=True)"""
    while True:
        data = get_gps_data() or {}
        if not data.get("fix"):
            print("[GPS_LOGGER] Pas de fix GPS, aucune donnée enregistrée.")
            time.sleep(interval)
            continue

        path = LOG_DIR / f"gps_{datetime.date.today()}.csv"
        newfile = not path.exists()

        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if newfile:
                w.writerow(["timestamp_utc", "latitude", "longitude", "altitude", "sats", "fix"])

            row = [
                datetime.datetime.utcnow().isoformat(),
                data.get("latitude"),
                data.get("longitude"),
                data.get("altitude"),
                data.get("satellites"),
                data.get("fix"),
            ]
            w.writerow(row)
            print(f"[GPS_LOGGER] Ligne écrite : {row}")

        time.sleep(interval)


if __name__ == "__main__":
    print("[GPS_LOGGER] Démarrage en mode test (intervalle = 5s)")
    start_gps_loop()  # 🚀 indispensable pour lancer la lecture GPS
    log_loop(5)
