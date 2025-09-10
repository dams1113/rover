import threading
import asyncio
import sys

from bot import discord_bot
from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop


def main():
    print("[MAIN] Démarrage du Rover...")

    # Démarrer la boucle GPS
    try:
        start_gps_loop()
        print("[MAIN] Boucle GPS démarrée")
    except Exception as e:
        print(f"[MAIN][ERREUR] Impossible de démarrer la boucle GPS : {e}", file=sys.stderr)

    # Démarrer le logger GPS
    try:
        threading.Thread(target=log_loop, args=(30,), daemon=True).start()
        print("[MAIN] GPS Logger lancé (intervalle = 30s)")
    except Exception as e:
        print(f"[MAIN][ERREUR] Impossible de lancer le logger GPS : {e}", file=sys.stderr)

    # Démarrer le bot Discord
    try:
        print("[MAIN] Lancement du bot Discord...")
        asyncio.run(discord_bot.client.start(discord_bot.TOKEN))
    except Exception as e:
        print(f"[MAIN][ERREUR] Le bot Discord a planté : {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
def gps_loop():
    """Boucle de lecture GPS en tâche de fond"""
    if not GPS_PORT:
        print("[GPS ERROR] Aucun port GPS détecté (/dev/ttyACM0 ou /dev/serial0)")
        return

    try:
        ser = serial.Serial(GPS_PORT, GPS_BAUDRATE, timeout=GPS_TIMEOUT)
        print(f"[GPS] Boucle démarrée sur {GPS_PORT} à {GPS_BAUDRATE} bauds")
    except Exception as e:
        print(f"[GPS ERROR] Impossible d'ouvrir {GPS_PORT}: {e}")
        return

    while True:
        try:
            line = ser.readline().decode(errors="ignore").strip()
            if line:
                print(f"[GPS DEBUG] Trame brute: {line}")   # <== ajout
            if line.startswith("$"):
                parse_nmea_sentence(line)
        except Exception as e:
            print(f"[GPS ERROR] {e}")
        time.sleep(0.1)
