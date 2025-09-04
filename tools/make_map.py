# tools/make_map.py
"""
Générer une carte interactive (Folium/Leaflet) à partir d'un ou plusieurs logs GPS (CSV).
Usage :
  python3 tools/make_map.py --logs logs --out map/rover_map.html --days 3
  python3 tools/make_map.py --file logs/gps_2025-09-03.csv
"""

import argparse, pathlib, csv, datetime, folium

def read_points_from_csv(path):
    pts = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except Exception:
                continue
            pts.append({
                "lat": lat,
                "lon": lon,
                "ts": row.get("timestamp_utc"),
                "sats": row.get("sats", ""),
                "hdop": row.get("hdop", ""),
                "alt": row.get("altitude", row.get("altitude_m", "")),
            })
    return pts

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs", help="Dossier contenant les CSV")
    ap.add_argument("--file", help="Fichier CSV unique")
    ap.add_argument("--out", default="map/rover_map.html", help="Fichier HTML de sortie")
    ap.add_argument("--days", type=int, default=1, help="Nb de jours à inclure (si --file absent)")
    args = ap.parse_args()

    logs = []
    if args.file:
        logs = [args.file]
    else:
        base = pathlib.Path(args.logs)
        today = datetime.date.today()
        for i in range(args.days):
            d = today - datetime.timedelta(days=i)
            p = base / f"gps_{d.isoformat()}.csv"
            if p.exists():
                logs.append(str(p))

    if not logs:
        raise SystemExit("Pas de fichiers trouvés")

    all_pts = []
    for p in sorted(logs):
        all_pts.extend(read_points_from_csv(p))

    if not all_pts:
        raise SystemExit("Pas de points valides")

    start = all_pts[0]
    m = folium.Map(location=[start["lat"], start["lon"]], zoom_start=17, control_scale=True)

    latlons = [(p["lat"], p["lon"]) for p in all_pts]
    folium.PolyLine(latlons, weight=3, opacity=0.8).add_to(m)
    folium.Marker(latlons[0], tooltip="Départ").add_to(m)
    folium.Marker(latlons[-1], tooltip="Arrivée").add_to(m)

    for idx, p in enumerate(all_pts):
        if idx % 50 == 0:
            folium.CircleMarker(
                location=[p["lat"], p["lon"]],
                radius=2, fill=True, fill_opacity=0.9,
                tooltip=f"{p['ts']} | sats={p['sats']} hdop={p['hdop']}"
            ).add_to(m)

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out_path))
    print(f"Carte générée : {out_path}")

if __name__ == "__main__":
    main()
