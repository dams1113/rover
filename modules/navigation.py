# modules/navigation.py
import math
import time
from modules import gps_reader, motors

# Rayon moyen de la Terre en mètres
EARTH_RADIUS = 6371000  

def haversine(lat1, lon1, lat2, lon2):
    """Distance en mètres entre 2 coordonnées GPS (lat/lon en degrés)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * EARTH_RADIUS * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def bearing(lat1, lon1, lat2, lon2):
    """Azimut en degrés depuis le point 1 vers le point 2."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1)*math.sin(phi2) - math.sin(phi1)*math.cos(phi2)*math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360

def goto(lat_target, lon_target, tolerance=2.0, step_time=1.5):
    """
    Déplace le rover vers une coordonnée GPS cible.
    - lat_target, lon_target : cible en degrés
    - tolerance : rayon de tolérance (m)
    - step_time : durée des pas en secondes
    """
    print(f"[GOTO] Navigation vers {lat_target}, {lon_target} (tolérance {tolerance} m)")

    while True:
        gps = gps_reader.get_gps_data()
        if not gps or not gps.get("fix"):
            print("[GOTO] ❌ Pas de fix GPS...")
            time.sleep(2)
            continue

        lat, lon = gps["latitude"], gps["longitude"]
        dist = haversine(lat, lon, lat_target, lon_target)

        if dist < tolerance:
            motors.stop()
            print("🎯 Objectif atteint")
            return True

        # Sans boussole : stratégie simpliste
        az = bearing(lat, lon, lat_target, lon_target)
        print(f"[GOTO] 📍 Position: {lat:.6f}, {lon:.6f}")
        print(f"[GOTO] 🎯 Distance: {dist:.1f} m | Azimut cible: {az:.1f}°")

        # Avance par petits pas
        motors.forward(speed=50, duration=step_time)
        time.sleep(step_time)

        # Stop pour laisser le temps de recalculer
        motors.stop()
        time.sleep(0.5)
