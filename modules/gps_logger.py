import csv, pathlib, datetime, time
from modules.gps_reader import get_gps_data

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def log_loop(interval=30):
    """Écrit la position toutes les X secondes"""
    while True:
        data = get_gps_data()
        if data and data.get("fix"):
            path = LOG_DIR / f"gps_{datetime.date.today()}.csv"
            newfile = not path.exists()
            with path.open("a", newline="") as f:
                w = csv.writer(f)
                if newfile:
                    w.writerow(["timestamp_utc","latitude","longitude","altitude","sats"])
                w.writerow([
                    datetime.datetime.utcnow().isoformat(),
                    data["latitude"], data["longitude"],
                    data["altitude"], data["satellites"]
                ])
        time.sleep(interval)
if __name__ == "__main__":
    log_loop(5)  # log toutes les 5 secondes
