# modules/gps_logger.py
import csv
import pathlib
import datetime
import time
from modules.gps_reader import start_gps_loop, get_gps_data

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def log_loop(interval=30):
    """Écrit une ligne GPS seulement si fix valide"""
    print("[GPS_LOGGER] Logger démarré")
    start_gps_loop()

    while True:
        data = get_gps_data()
        if not data.get("fix"):
            print("[GPS_LOGGER] Pas de fix GPS, ligne ignorée")
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
                data["latitude"],
                data["longitude"],
                data["altitude"],
                data["satellites"],
                data["fix"],
            ])

        print(f"[GPS_LOGGER] ✅ Ligne écrite : {data}")
        time.sleep(interval)

if __name__ == "__main__":
    log_loop(5)
