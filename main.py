import threading
import asyncio
import sys
import time

from bot import discord_bot
from modules.gps_reader import start_gps_loop, get_gps_data
from modules.gps_logger import log_loop

def main():
    print("[MAIN] 🚀 Démarrage du Rover...")

    # GPS Loop
    try:
        start_gps_loop()
        print("[MAIN] ✅ Boucle GPS démarrée")
    except Exception as e:
        print(f"[MAIN][ERREUR] Impossible de démarrer la boucle GPS : {e}", file=sys.stderr)

    # GPS Logger (écrit dans logs/gps_*.csv)
    try:
        t = threading.Thread(target=log_loop, args=(30,), daemon=True)
        t.start()
        print("[MAIN] ✅ GPS Logger lancé (intervalle = 30s)")
    except Exception as e:
        print(f"[MAIN][ERREUR] Impossible de lancer le logger GPS : {e}", file=sys.stderr)

    # Petit test pour confirmer qu’on reçoit bien les données
    time.sleep(5)
    print("[MAIN] Exemple données GPS:", get_gps_data())

    # Discord Bot
    try:
        print("[MAIN] 🚀 Lancement du bot Discord...")
        asyncio.run(discord_bot.client.start(discord_bot.TOKEN))
    except Exception as e:
        print(f"[MAIN][ERREUR] Le bot Discord a planté : {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
