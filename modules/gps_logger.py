import csv
import pathlib
import datetime
import time
from modules.gps_reader import get_gps_data

# Chemin absolu vers le dossier du projet
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def log_loop(interval=30):
    """Écrit la position toutes les X secondes dans logs/gps_YYYY-MM-DD.csv"""
    while True:
        data = get_gps_data() or {}
        path = LOG_DIR / f"gps_{datetime.date.today()}.csv"
        newfile = not path.exists()

        with path.open("a", newline="") as f:
            w = csv.writer(f)
            if newfile:
                w.writerow(["timestamp_utc", "latitude", "longitude", "altitude", "sats", "fix"])

            # Écrit toujours une ligne, même sans fix
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
