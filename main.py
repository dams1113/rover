import threading
import asyncio
import sys

from bot import discord_bot
from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop


def main():
    print("[MAIN] 🚀 Démarrage du Rover...")

    # Lancer la boucle GPS (thread)
    try:
        start_gps_loop()
        print("[MAIN] ✅ Boucle GPS démarrée")
    except Exception as e:
        print(f"[MAIN][ERREUR] ❌ Impossible de démarrer la boucle GPS : {e}", file=sys.stderr)

    # Lancer le logger GPS (thread)
    try:
        t = threading.Thread(target=log_loop, args=(30,), daemon=True)
        t.start()
        print("[MAIN] ✅ GPS Logger lancé (intervalle = 30s)")
    except Exception as e:
        print(f"[MAIN][ERREUR] ❌ Impossible de lancer le logger GPS : {e}", file=sys.stderr)

    # Lancer le bot Discord
    try:
        print("[MAIN] 🤖 Lancement du bot Discord...")
        asyncio.run(discord_bot.client.start(discord_bot.TOKEN))
    except Exception as e:
        print(f"[MAIN][ERREUR] ❌ Le bot Discord a planté : {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
