"""
Superposer plusieurs fichiers CSV GPS sur une seule carte Folium.
Chaque trace est une couche distincte + HeatMap/points optionnels.

Usage :
  python3 tools/multi_map.py --in logs/gps_2025-09-03.csv --in logs/gps_2025-09-04.csv \
      --out map/multi_map.html --basemap positron --heatmap --points
"""

import argparse, pathlib, csv, folium, math
from folium.plugins import HeatMap, MarkerCluster


def is_valid_coord(val):
    """Retourne True si val est un nombre valide (float)"""
    if val is None or val == "":
        return False
    try:
        f = float(val)
        return not math.isnan(f)
    except:
        return False


def read_points_csv(path):
    pts = []
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            lat = row.get("latitude_filt") or row.get("latitude")
            lon = row.get("longitude_filt") or row.get("longitude")

            if not (is_valid_coord(lat) and is_valid_coord(lon)):
                continue

            ts = row.get("timestamp_utc", "")
            pts.append((float(lat), float(lon), ts))
    return pts


def add_basemap(m, basemap, tiles_url=None, tiles_attrib=""):
    if tiles_url:
        folium.TileLayer(tiles=tiles_url, attr=tiles_attrib, name="Custom").add_to(m)
        return
    if basemap == "positron":
        folium.TileLayer("CartoDB positron", name="CartoDB Positron").add_to(m)
    elif basemap == "dark":
        folium.TileLayer("CartoDB dark_matter", name="CartoDB Dark").add_to(m)
    elif basemap == "terrain":
        folium.TileLayer("Stamen Terrain").add_to(m)
    elif basemap == "toner":
        folium.TileLayer("Stamen Toner").add_to(m)
    else:
        folium.TileLayer("OpenStreetMap").add_to(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inputs", action="append", required=True, help="CSV à superposer")
    ap.add_argument("--out", default="map/multi_map.html", help="HTML de sortie")
    ap.add_argument("--basemap", choices=["osm","positron","dark","terrain","toner"], default="osm")
    ap.add_argument("--tiles-url")
    ap.add_argument("--tiles-attrib", default="")
    ap.add_argument("--heatmap", action="store_true")
    ap.add_argument("--points", action="store_true")
    args = ap.parse_args()

    all_tracks = []
    for p in args.inputs:
        pts = read_points_csv(p)
        if pts:
            all_tracks.append((p, pts))

    if not all_tracks:
        raise SystemExit("Aucun point GPS valide trouvé")

    first_lat, first_lon, _ = all_tracks[0][1][0]
    m = folium.Map(location=[first_lat, first_lon], zoom_start=16, control_scale=True)
    add_basemap(m, args.basemap, args.tiles_url, args.tiles_attrib)

    colors = ["red","blue","green","purple","orange","pink","gray","black"]
    heat_pts = []

    for i, (name, pts) in enumerate(all_tracks):
        latlons = [(lat, lon) for (lat, lon, _) in pts]
        color = colors[i % len(colors)]
        grp = folium.FeatureGroup(name=f"Trace {i+1}: {pathlib.Path(name).name}", show=True)
        folium.PolyLine(latlons, color=color, weight=3, opacity=0.9).add_to(grp)
        folium.Marker(latlons[0], tooltip=f"Départ {i+1}").add_to(grp)
        folium.Marker(latlons[-1], tooltip=f"Arrivée {i+1}").add_to(grp)
        grp.add_to(m)
        heat_pts.extend(latlons)

        if args.points:
            cl = MarkerCluster(name=f"Points {i+1}", show=False)
            for (lat, lon, ts) in pts:
                folium.CircleMarker(location=[lat, lon], radius=2,
                                    fill=True, fill_opacity=0.9, tooltip=ts).add_to(cl)
            cl.add_to(m)

    if args.heatmap and heat_pts:
        HeatMap(heat_pts, name="HeatMap densité").add_to(m)

    folium.LayerControl().add_to(m)
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    m.save(args.out)
    print(f"[OK] Carte générée : {args.out}")


if __name__ == "__main__":
    main()
