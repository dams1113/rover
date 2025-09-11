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

    # Démarrer le logger GPS (en arrière-plan)
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
