# main.py
import threading
import asyncio
import sys

from modules.gps_reader import start_gps_loop
from modules.gps_logger import log_loop
from bot import discord_bot


def main():
    print("[MAIN] 🚀 Démarrage du Rover...")

    # --- GPS Loop ---
    try:
        start_gps_loop()
        print("[MAIN] ✅ Thread GPS démarré")
    except Exception as e:
        print(f"[MAIN][ERREUR] GPS non démarré : {e}", file=sys.stderr)

    # --- GPS Logger ---
    try:
        threading.Thread(target=log_loop, args=(30,), daemon=True).start()
        print("[MAIN] ✅ Logger GPS lancé (intervalle = 30s)")
    except Exception as e:
        print(f"[MAIN][ERREUR] Logger non démarré : {e}", file=sys.stderr)

    # --- Discord Bot ---
    try:
        print("[MAIN] 🤖 Lancement du bot Discord...")
        asyncio.run(discord_bot.client.start(discord_bot.TOKEN))
    except Exception as e:
        print(f"[MAIN][ERREUR] Bot planté : {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
