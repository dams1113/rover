"""
navigation.py - Contrôle GPS et navigation du Rover
Version adaptée sans dépendance à robot_hat (Arduino gère les capteurs)
"""

import math
import time
from modules.gps_reader import get_gps_data
from modules import motors
from modules import arduino_link


def _distance(lat1, lon1, lat2, lon2):
    """Calcule la distance entre deux points GPS en mètres."""
    R = 6371000  # rayon Terre (m)
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing(lat1, lon1, lat2, lon2):
    """Calcule l’angle de cap entre deux coordonnées."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def goto(target_lat, target_lon, tolerance=2.5):
    """
    Déplace le rover jusqu’à la position GPS donnée.
    Le capteur ultrason / IR est géré par l’Arduino (télémétrie série).
    """
    print(f"[NAV] 🚀 Navigation vers {target_lat}, {target_lon}")

    gps = get_gps_data()
    if not gps or not gps.get("fix"):
        print("[NAV] ❌ Pas de fix GPS — navigation impossible.")
        return False

    current_lat = gps["latitude"]
    current_lon = gps["longitude"]

    distance = _distance(current_lat, current_lon, target_lat, target_lon)
    print(f"[NAV] Distance initiale : {distance:.2f} m")

    if distance < tolerance:
        print("[NAV] ✅ Déjà sur la position cible.")
        return True

    # Avance tant que la distance est supérieure à la tolérance
    while distance > tolerance:
        gps = get_gps_data()
        if not gps or not gps.get("fix"):
            print("[NAV] ⚠️ GPS perdu, arrêt.")
            motors.stop()
            arduino_link.send_cmd("S")
            return False

        current_lat = gps["latitude"]
        current_lon = gps["longitude"]
        distance = _distance(current_lat, current_lon, target_lat, target_lon)
        print(f"[NAV] 📍 Distance restante : {distance:.2f} m")

        # Mouvement avant
        motors.forward(speed=50, duration=1)
        arduino_link.send_cmd("F")
        time.sleep(1)

        # Arrêt et nouvelle mesure
        motors.stop()
        arduino_link.send_cmd("S")
        time.sleep(0.5)

        # Si la distance ne diminue pas, tentative d’ajustement
        if distance < tolerance:
            break

    print("[NAV] ✅ Objectif atteint !")
    motors.stop()
    arduino_link.send_cmd("S")
    return True
