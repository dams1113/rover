def read_points_csv(path):
    pts = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                lat = float(row.get("latitude", "") or "nan")
                lon = float(row.get("longitude", "") or "nan")
            except ValueError:
                continue

            if not lat or not lon or lat == "nan" or lon == "nan":
                continue

            ts = row.get("timestamp_utc", "")
            pts.append((lat, lon, ts))
    return pts
